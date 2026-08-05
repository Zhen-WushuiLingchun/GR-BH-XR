using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR;

namespace GRBHXR
{
    [ExecuteAlways]
    public sealed class BlackHoleLensXrControllerControls : MonoBehaviour
    {
        [SerializeField] private BlackHoleLensAnchorControls controls;
        [SerializeField] private BlackHoleLensFloatingPanel floatingPanel;
        [SerializeField] private BlackHoleLensSettingsPanel settingsPanel;
        [SerializeField] private BlackHoleLensRuntimeSettings runtimeSettings;
        [SerializeField] private BlackHoleObserverRigControls observerRigControls;
        [SerializeField] private bool enableControllerInput = true;
        [SerializeField] private bool walkObserverOnRightStick = true;
        [SerializeField] private bool turnObserverOnLeftStick = true;
        [SerializeField] private bool aimLensOnRightGrip = true;
        [SerializeField] private float observerYawDegreesPerSecond = 45.0f;
        [SerializeField] private float hotSpotRadiusPerSecond = 3.0f;
        [SerializeField] private float hotSpotPhaseRadiansPerSecond = 1.4f;
        [SerializeField] private float spinPerSecond = 0.4f;
        [SerializeField] private float massPerSecond = 0.3f;
        [SerializeField] private float stickDeadZone = 0.15f;
        [SerializeField] private float panelToggleCooldownSeconds = 0.25f;

        private readonly List<InputDevice> devices = new List<InputDevice>();
        private bool previousRightPrimaryButton;
        private bool previousRightSecondaryButton;
        private bool previousRightTriggerButton;
        private bool previousLeftPrimaryButton;
        private bool previousLeftSecondaryButton;
        private bool previousLeftTriggerButton;
        private int rightDeviceCount;
        private int leftDeviceCount;
        private string rightDeviceName = "none";
        private string leftDeviceName = "none";
        private Vector2 rightAxis;
        private Vector2 leftAxis;
        private bool rightPrimaryButton;
        private bool rightSecondaryButton;
        private bool leftPrimaryButton;
        private bool leftSecondaryButton;
        private int loggedRightDeviceCount = -1;
        private int loggedLeftDeviceCount = -1;
        private string loggedRightDeviceName = "";
        private string loggedLeftDeviceName = "";
        private float nextPanelToggleTime;

        private void Awake()
        {
            ResolveReferences();
        }

        private void OnEnable()
        {
            ResolveReferences();
        }

        private void Update()
        {
            if (!enableControllerInput || !Application.isPlaying)
            {
                return;
            }

            ResolveReferences();
            PollRightController();
            PollLeftController();
        }

        private void PollRightController()
        {
            if (!TryGetDevice(InputDeviceCharacteristics.Right, out InputDevice right))
            {
                previousRightPrimaryButton = false;
                previousRightSecondaryButton = false;
                previousRightTriggerButton = false;
                return;
            }

            bool panelOpen = settingsPanel != null && settingsPanel.IsVisible;
            bool hasAxis = TryGetAxis(right, out Vector2 axis);
            bool leftGripHeld = TryGetDevice(InputDeviceCharacteristics.Left, out InputDevice leftForChord)
                && TryGetButton(leftForChord, CommonUsages.gripButton);
            if (hasAxis && panelOpen)
            {
                settingsPanel.Navigate(axis);
            }
            else if (hasAxis && leftGripHeld)
            {
                // Chord: LEFT grip + RIGHT stick = continuous metric control.
                // X adjusts spin (can cross zero: the mirror-system
                // falsification test), Y adjusts mass. The live tracer
                // re-solves within a pass, so the response is first
                // principles, not a styling change.
                var liveTracer = FindAnyObjectByType<BlackHoleLiveTracer>();
                if (liveTracer != null)
                {
                    liveTracer.AdjustSpin(axis.x * spinPerSecond * Time.deltaTime);
                    liveTracer.AdjustMass(axis.y * massPerSecond * Time.deltaTime);
                }
            }
            else if (hasAxis && walkObserverOnRightStick && observerRigControls != null)
            {
                // Walk in the pushed direction relative to where the user
                // faces; the rig decomposes it onto radial/polar/azimuthal
                // motion through the keyframe grid.
                observerRigControls.AddWalkInput(axis, Time.deltaTime);
            }

            // A activates only inside the panel. Bare A no longer re-places the
            // lens: an accidental press snapped the black hole to the current
            // gaze, which read as broken rotation. Use the panel button instead.
            bool primary = TryGetButton(right, CommonUsages.primaryButton);
            rightPrimaryButton = primary;
            if (primary && !previousRightPrimaryButton && panelOpen)
            {
                settingsPanel.ActivateSelected();
            }
            previousRightPrimaryButton = primary;

            bool trigger = TryGetButton(right, CommonUsages.triggerButton);
            if (trigger && !previousRightTriggerButton && panelOpen)
            {
                settingsPanel.ActivateSelected();
            }
            previousRightTriggerButton = trigger;

            bool secondary = TryGetButton(right, CommonUsages.secondaryButton);
            rightSecondaryButton = secondary;
            if (secondary && !previousRightSecondaryButton)
            {
                TogglePanelFromController();
            }
            previousRightSecondaryButton = secondary;

            bool rightGrip = TryGetButton(right, CommonUsages.gripButton);
            if (rightGrip && panelOpen && settingsPanel != null)
            {
                settingsPanel.DragToRay(GetDevicePositionOrCamera(right), GetDeviceForwardOrCamera(right));
            }
            else if (rightGrip && !panelOpen && aimLensOnRightGrip && controls != null)
            {
                // Grab-and-aim: while the right grip is held, the lens anchor
                // follows the controller ray, dragging the black hole across
                // the sky. This is scene placement (a rigid re-aim of the
                // cached lens field), not observer motion or spin change.
                controls.AimAlongWorldDirection(GetDeviceForwardOrCamera(right));
            }
        }

        private void PollLeftController()
        {
            if (!TryGetDevice(InputDeviceCharacteristics.Left, out InputDevice left))
            {
                previousLeftPrimaryButton = false;
                previousLeftSecondaryButton = false;
                previousLeftTriggerButton = false;
                return;
            }

            bool gripHeld = TryGetButton(left, CommonUsages.gripButton);
            bool panelOpen = settingsPanel != null && settingsPanel.IsVisible;
            bool hasAxis = TryGetAxis(left, out Vector2 axis);
            if (hasAxis && runtimeSettings != null && gripHeld && !panelOpen)
            {
                runtimeSettings.AddDiskHotSpotPhase(axis.x * hotSpotPhaseRadiansPerSecond * Time.deltaTime);
                runtimeSettings.AddDiskHotSpotRadius(axis.y * hotSpotRadiusPerSecond * Time.deltaTime);
            }
            else if (hasAxis && !gripHeld && !panelOpen && turnObserverOnLeftStick && observerRigControls != null)
            {
                observerRigControls.AddYawDegrees(axis.x * observerYawDegreesPerSecond * Time.deltaTime);
            }

            // Disk shortcuts stay quiet while the panel is open so panel
            // navigation cannot double as scene mutation.
            bool primary = TryGetButton(left, CommonUsages.primaryButton);
            leftPrimaryButton = primary;
            if (primary && !previousLeftPrimaryButton && runtimeSettings != null && !panelOpen)
            {
                runtimeSettings.ToggleDiskVisualMode();
            }
            previousLeftPrimaryButton = primary;

            bool secondary = TryGetButton(left, CommonUsages.secondaryButton);
            leftSecondaryButton = secondary;
            if (secondary && !previousLeftSecondaryButton && runtimeSettings != null && !panelOpen)
            {
                runtimeSettings.CycleDiskAuditMode();
            }
            previousLeftSecondaryButton = secondary;

            if (settingsPanel != null)
            {
                bool trigger = TryGetButton(left, CommonUsages.triggerButton);
                if (trigger && !previousLeftTriggerButton && settingsPanel.IsVisible)
                {
                    settingsPanel.ActivateSelected();
                }
                previousLeftTriggerButton = trigger;
                if (gripHeld)
                {
                    settingsPanel.DragToRay(GetDevicePositionOrCamera(left), GetDeviceForwardOrCamera(left));
                }
            }
        }

        public string StatusText()
        {
            RefreshDeviceSummary(InputDeviceCharacteristics.Right);
            RefreshDeviceSummary(InputDeviceCharacteristics.Left);
            // theta reports BOTH the continuously walked value and the row the
            // renderer is actually bound to. They differ by up to half a row
            // spacing (7.5 deg on a 15 deg grid), and showing only the walked
            // value made this readout disagree with the roam status line.
            var roam = FindAnyObjectByType<BlackHoleRoamKeyframes>();
            string boundTheta = roam != null ? $"{roam.BoundThetaDeg:F0}" : "?";
            string observer = observerRigControls != null
                ? $"yaw={observerRigControls.VirtualYawDegrees:F0} r={observerRigControls.VirtualRadiusM:F2}M " +
                  $"theta={observerRigControls.VirtualThetaDeg:F0}->{boundTheta} az={observerRigControls.VirtualAzimuthDeg:F0}"
                : "observer rig missing";
            var tracer = FindAnyObjectByType<BlackHoleLiveTracer>();
            string metric = tracer != null
                ? $"M={tracer.MassValue:F2} a={tracer.SpinValue:F3}"
                : "M/a: live tracer absent";
            return
                $"R ctrl n={rightDeviceCount} axis=({rightAxis.x:F2},{rightAxis.y:F2}) A={rightPrimaryButton} B={rightSecondaryButton}\n" +
                $"L ctrl n={leftDeviceCount} axis=({leftAxis.x:F2},{leftAxis.y:F2}) X={leftPrimaryButton} Y={leftSecondaryButton}\n" +
                $"R stick walks where you face ({observer}); L stick turns; R grip drags the hole\n" +
                $"L grip + R stick changes the metric ({metric})\n" +
                "Quasi-static keyframe grid; azimuth exact by axisymmetry; no boost between frames.";
        }

        public void TogglePanelFromController()
        {
            if (Time.unscaledTime < nextPanelToggleTime)
            {
                return;
            }
            nextPanelToggleTime = Time.unscaledTime + Mathf.Max(panelToggleCooldownSeconds, 0.05f);

            if (settingsPanel != null)
            {
                if (settingsPanel.IsVisible)
                {
                    settingsPanel.Close();
                }
                else
                {
                    settingsPanel.Open();
                }
                Debug.Log($"GR-BH-XR settings panel visible={settingsPanel.IsVisible} (right B).");
            }
            else if (floatingPanel != null)
            {
                floatingPanel.ToggleVisible();
            }
        }

        private bool TryGetDevice(InputDeviceCharacteristics handedness, out InputDevice device)
        {
            devices.Clear();
            InputDevices.GetDevicesWithCharacteristics(
                InputDeviceCharacteristics.Controller | InputDeviceCharacteristics.HeldInHand | handedness,
                devices
            );
            RecordDeviceSummary(handedness, devices);
            if (devices.Count > 0)
            {
                device = devices[0];
                return true;
            }

            device = default;
            return false;
        }

        private bool TryGetAxis(InputDevice device, out Vector2 axis)
        {
            if (!device.TryGetFeatureValue(CommonUsages.primary2DAxis, out axis))
            {
                axis = Vector2.zero;
                return false;
            }

            axis.x = Mathf.Abs(axis.x) >= stickDeadZone ? axis.x : 0.0f;
            axis.y = Mathf.Abs(axis.y) >= stickDeadZone ? axis.y : 0.0f;
            if ((device.characteristics & InputDeviceCharacteristics.Right) != 0)
            {
                rightAxis = axis;
            }
            else if ((device.characteristics & InputDeviceCharacteristics.Left) != 0)
            {
                leftAxis = axis;
            }
            return axis.sqrMagnitude > 0.0f;
        }

        private static bool TryGetButton(InputDevice device, InputFeatureUsage<bool> usage)
        {
            return device.TryGetFeatureValue(usage, out bool pressed) && pressed;
        }

        private void ResolveReferences()
        {
            if (controls == null)
            {
                controls = GetComponent<BlackHoleLensAnchorControls>();
            }
            if (controls == null)
            {
                controls = FindAnyObjectByType<BlackHoleLensAnchorControls>();
            }
            if (floatingPanel == null)
            {
                floatingPanel = FindAnyObjectByType<BlackHoleLensFloatingPanel>();
            }
            if (settingsPanel == null)
            {
                settingsPanel = FindAnyObjectByType<BlackHoleLensSettingsPanel>();
            }
            if (runtimeSettings == null)
            {
                runtimeSettings = FindAnyObjectByType<BlackHoleLensRuntimeSettings>();
            }
            if (observerRigControls == null)
            {
                observerRigControls = FindAnyObjectByType<BlackHoleObserverRigControls>();
            }
        }

        private Vector3 GetDevicePositionOrCamera(InputDevice device)
        {
            if (device.TryGetFeatureValue(CommonUsages.devicePosition, out Vector3 position))
            {
                return observerRigControls != null
                    ? observerRigControls.TrackingToWorldPoint(position)
                    : position;
            }
            return Camera.main != null ? Camera.main.transform.position : Vector3.zero;
        }

        private Vector3 GetDeviceForwardOrCamera(InputDevice device)
        {
            if (device.TryGetFeatureValue(CommonUsages.deviceRotation, out Quaternion rotation))
            {
                Vector3 direction = rotation * Vector3.forward;
                return observerRigControls != null
                    ? observerRigControls.TrackingToWorldDirection(direction)
                    : direction;
            }
            return Camera.main != null ? Camera.main.transform.forward : Vector3.forward;
        }

        private void RefreshDeviceSummary(InputDeviceCharacteristics handedness)
        {
            devices.Clear();
            InputDevices.GetDevicesWithCharacteristics(
                InputDeviceCharacteristics.Controller | InputDeviceCharacteristics.HeldInHand | handedness,
                devices
            );
            RecordDeviceSummary(handedness, devices);
        }

        private void RecordDeviceSummary(InputDeviceCharacteristics handedness, List<InputDevice> foundDevices)
        {
            string name = foundDevices.Count > 0 ? foundDevices[0].name : "none";
            if ((handedness & InputDeviceCharacteristics.Right) != 0)
            {
                rightDeviceCount = foundDevices.Count;
                rightDeviceName = name;
                LogDeviceChange("Right", rightDeviceCount, rightDeviceName, ref loggedRightDeviceCount, ref loggedRightDeviceName);
                if (foundDevices.Count == 0)
                {
                    rightAxis = Vector2.zero;
                    rightPrimaryButton = false;
                    rightSecondaryButton = false;
                }
            }
            if ((handedness & InputDeviceCharacteristics.Left) != 0)
            {
                leftDeviceCount = foundDevices.Count;
                leftDeviceName = name;
                LogDeviceChange("Left", leftDeviceCount, leftDeviceName, ref loggedLeftDeviceCount, ref loggedLeftDeviceName);
                if (foundDevices.Count == 0)
                {
                    leftAxis = Vector2.zero;
                    leftPrimaryButton = false;
                    leftSecondaryButton = false;
                }
            }
        }

        private static void LogDeviceChange(
            string label,
            int count,
            string name,
            ref int loggedCount,
            ref string loggedName
        )
        {
            if (!Application.isPlaying || (count == loggedCount && name == loggedName))
            {
                return;
            }
            loggedCount = count;
            loggedName = name;
            Debug.Log($"GR-BH-XR XR controller {label}: count={count}, firstDevice={name}");
        }
    }
}
