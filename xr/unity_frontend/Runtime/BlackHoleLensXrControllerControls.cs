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
        [SerializeField] private bool enableControllerInput = true;
        [SerializeField] private bool yawPitchOnRightStick = true;
        [SerializeField] private bool rollOnLeftStick = true;
        // Default off: with the hold-to-rotate gate on, users could not tell
        // whether the sticks worked at all. The stick dead zone already filters
        // most accidental input; re-enable per scene if drift shows up.
        [SerializeField] private bool requireGripOrTriggerForStickRotation;
        [SerializeField] private float yawPitchDegreesPerSecond = 45.0f;
        [SerializeField] private float rollDegreesPerSecond = 45.0f;
        [SerializeField] private float stickDeadZone = 0.15f;

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
            if (controls == null)
            {
                return;
            }

            PollRightController();
            PollLeftController();
        }

        private void PollRightController()
        {
            if (!TryGetDevice(InputDeviceCharacteristics.Right, out InputDevice right))
            {
                previousRightPrimaryButton = false;
                previousRightSecondaryButton = false;
                return;
            }

            bool rotationHeld = !requireGripOrTriggerForStickRotation || IsRotationModifierHeld(right);
            bool panelOpen = settingsPanel != null && settingsPanel.IsVisible;
            if (TryGetAxis(right, out Vector2 axis) && panelOpen)
            {
                settingsPanel.Navigate(axis);
            }
            else if (yawPitchOnRightStick && rotationHeld && axis.sqrMagnitude > 0.0f)
            {
                controls.AddYawDegrees(axis.x * yawPitchDegreesPerSecond * Time.deltaTime);
                controls.AddPitchDegrees(axis.y * yawPitchDegreesPerSecond * Time.deltaTime);
            }

            bool primary = TryGetButton(right, CommonUsages.primaryButton);
            rightPrimaryButton = primary;
            if (primary && !previousRightPrimaryButton)
            {
                if (panelOpen)
                {
                    settingsPanel.ActivateSelected();
                }
                else
                {
                    controls.ResetPose();
                }
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
                if (settingsPanel != null)
                {
                    settingsPanel.ToggleVisible();
                }
                else if (floatingPanel != null)
                {
                    floatingPanel.ToggleVisible();
                }
            }
            previousRightSecondaryButton = secondary;

            if (settingsPanel != null && TryGetButton(right, CommonUsages.gripButton))
            {
                settingsPanel.DragToRay(GetDevicePositionOrCamera(right), GetDeviceForwardOrCamera(right));
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

            bool rotationHeld = !requireGripOrTriggerForStickRotation || IsRotationModifierHeld(left);
            if (rollOnLeftStick && rotationHeld && TryGetAxis(left, out Vector2 axis))
            {
                controls.AddRollDegrees(axis.x * rollDegreesPerSecond * Time.deltaTime);
            }

            bool primary = TryGetButton(left, CommonUsages.primaryButton);
            leftPrimaryButton = primary;
            if (primary && !previousLeftPrimaryButton && runtimeSettings != null)
            {
                runtimeSettings.ToggleDiskVisualMode();
            }
            previousLeftPrimaryButton = primary;

            bool secondary = TryGetButton(left, CommonUsages.secondaryButton);
            leftSecondaryButton = secondary;
            if (secondary && !previousLeftSecondaryButton && runtimeSettings != null)
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
                if (TryGetButton(left, CommonUsages.gripButton))
                {
                    settingsPanel.DragToRay(GetDevicePositionOrCamera(left), GetDeviceForwardOrCamera(left));
                }
            }
        }

        public string StatusText()
        {
            RefreshDeviceSummary(InputDeviceCharacteristics.Right);
            RefreshDeviceSummary(InputDeviceCharacteristics.Left);
            string gate = requireGripOrTriggerForStickRotation ? "hold grip/trigger + stick" : "stick rotates directly";
            return
                $"R ctrl n={rightDeviceCount} axis=({rightAxis.x:F2},{rightAxis.y:F2}) A={rightPrimaryButton} B={rightSecondaryButton}\n" +
                $"L ctrl n={leftDeviceCount} axis=({leftAxis.x:F2},{leftAxis.y:F2}) X={leftPrimaryButton} Y={leftSecondaryButton}\n" +
                gate;
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

        private static bool IsRotationModifierHeld(InputDevice device)
        {
            return TryGetButton(device, CommonUsages.triggerButton) ||
                   TryGetButton(device, CommonUsages.gripButton);
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
        }

        private static Vector3 GetDevicePositionOrCamera(InputDevice device)
        {
            if (device.TryGetFeatureValue(CommonUsages.devicePosition, out Vector3 position))
            {
                return position;
            }
            return Camera.main != null ? Camera.main.transform.position : Vector3.zero;
        }

        private static Vector3 GetDeviceForwardOrCamera(InputDevice device)
        {
            if (device.TryGetFeatureValue(CommonUsages.deviceRotation, out Quaternion rotation))
            {
                return rotation * Vector3.forward;
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
