using System;
using UnityEngine;

namespace GRBHXR
{
    [ExecuteAlways]
    public sealed class BlackHoleLensAnchorControls : MonoBehaviour
    {
        public enum DragMode
        {
            YawPitch,
            YawOnly
        }

        [SerializeField] private Transform lensAnchor;
        [SerializeField] private BlackHoleXrSkyShell skyShell;
        [SerializeField] private Camera targetCamera;
        [SerializeField] private BlackHoleXrHeadPoseDriver headPoseDriver;
        [SerializeField] private DragMode dragMode = DragMode.YawPitch;
        [SerializeField] private bool enableMouseKeyboardInput = true;
        // The Link stage yaw depends on the user's recenter direction, so world +Z
        // is not "in front of the user". Aim the lens at the tracked gaze once the
        // HMD pose becomes valid, instead of leaving it at world forward.
        [SerializeField] private bool alignToCameraOnFirstValidPose = true;
        [SerializeField] private float degreesPerPixel = 0.05f;
        [SerializeField] private float keyboardStepDegrees = 2.0f;
        [SerializeField] private float yawDegrees;
        [SerializeField] private float pitchDegrees;
        [SerializeField] private float rollDegrees;
        [SerializeField] private bool transferMapStale;
        [SerializeField] private float requestedObserverRadius = 100.0f;

        private bool isDragging;
        private Vector3 previousMousePosition;
        private bool oldInputUnavailable;
        private bool hasAlignedToCamera;
        private int playModeFrameCount;

        public float YawDegrees => yawDegrees;
        public float PitchDegrees => pitchDegrees;
        public float RollDegrees => rollDegrees;
        public bool TransferMapStale => transferMapStale;

        private void Awake()
        {
            ResolveReferences();
            ApplyPose();
        }

        private void OnEnable()
        {
            ResolveReferences();
            ApplyPose();
        }

        private void Update()
        {
            if (Application.isPlaying && alignToCameraOnFirstValidPose && !hasAlignedToCamera)
            {
                playModeFrameCount += 1;
                bool poseReady = headPoseDriver != null
                    ? headPoseDriver.PoseValid
                    : playModeFrameCount > 10;
                if (poseReady)
                {
                    AlignToCameraForward();
                }
            }

            if (!enableMouseKeyboardInput || oldInputUnavailable)
            {
                return;
            }

            try
            {
                PollMouseKeyboardInput();
            }
            catch (InvalidOperationException)
            {
                oldInputUnavailable = true;
                Debug.LogWarning(
                    "BlackHoleLensAnchorControls disabled legacy Input polling. " +
                    "Wire XR controller rays or UI buttons to the public control methods instead."
                );
            }
        }

        public void ApplyScreenDrag(Vector2 pixelDelta)
        {
            AddYawDegrees(pixelDelta.x * degreesPerPixel);
            if (dragMode == DragMode.YawPitch)
            {
                AddPitchDegrees(-pixelDelta.y * degreesPerPixel);
            }
        }

        public void AddYawDegrees(float deltaDegrees)
        {
            yawDegrees = NormalizeAngle(yawDegrees + deltaDegrees);
            ApplyPose();
        }

        public void AddPitchDegrees(float deltaDegrees)
        {
            pitchDegrees = Mathf.Clamp(pitchDegrees + deltaDegrees, -89.0f, 89.0f);
            ApplyPose();
        }

        public void AddRollDegrees(float deltaDegrees)
        {
            rollDegrees = NormalizeAngle(rollDegrees + deltaDegrees);
            ApplyPose();
        }

        public void SetYawDegrees(float value)
        {
            yawDegrees = NormalizeAngle(value);
            ApplyPose();
        }

        public void SetPitchDegrees(float value)
        {
            pitchDegrees = Mathf.Clamp(value, -89.0f, 89.0f);
            ApplyPose();
        }

        public void SetRollDegrees(float value)
        {
            rollDegrees = NormalizeAngle(value);
            ApplyPose();
        }

        public void ResetPose()
        {
            if (!AlignToCameraForward())
            {
                yawDegrees = 0.0f;
                pitchDegrees = 0.0f;
                rollDegrees = 0.0f;
                ApplyPose();
            }
        }

        public bool AlignToCameraForward()
        {
            ResolveReferences();
            if (targetCamera == null)
            {
                return false;
            }

            Vector3 forward = targetCamera.transform.forward;
            if (forward.sqrMagnitude < 1.0e-6f)
            {
                return false;
            }
            forward = forward.normalized;

            yawDegrees = NormalizeAngle(Mathf.Atan2(forward.x, forward.z) * Mathf.Rad2Deg);
            pitchDegrees = Mathf.Clamp(
                -Mathf.Asin(Mathf.Clamp(forward.y, -1.0f, 1.0f)) * Mathf.Rad2Deg,
                -89.0f,
                89.0f
            );
            rollDegrees = 0.0f;
            hasAlignedToCamera = true;
            ApplyPose();
            Debug.Log(
                $"GR-BH-XR lens anchor aligned to camera forward: yaw={yawDegrees:F1}, " +
                $"pitch={pitchDegrees:F1}, cameraForward={forward}"
            );
            return true;
        }

        public void RequestObserverRadiusChange(float newObserverRadius)
        {
            requestedObserverRadius = Mathf.Max(newObserverRadius, 1.0f);
            transferMapStale = true;
            Debug.LogWarning(
                "Observer-radius or apparent-size changes require a new transfer map. " +
                $"Requested r_obs={requestedObserverRadius:F3}; current static textures were not rescaled."
            );
        }

        public void ClearTransferMapStaleFlag()
        {
            transferMapStale = false;
        }

        public string StatusText()
        {
            string stale = transferMapStale ? "STALE" : "fixed";
            return
                "GR-BH-XR Lens Controls\n" +
                $"Yaw {yawDegrees:F1}  Pitch {pitchDegrees:F1}  Roll {rollDegrees:F1}\n" +
                "R stick: yaw/pitch  L stick: roll\n" +
                "A: aim at view  B: panel\n" +
                "Desktop: drag / arrows / Q E / R\n" +
                $"Size/r_obs: locked (map {stale})";
        }

        private void PollMouseKeyboardInput()
        {
            if (Input.GetMouseButtonDown(0))
            {
                isDragging = true;
                previousMousePosition = Input.mousePosition;
            }
            if (Input.GetMouseButtonUp(0))
            {
                isDragging = false;
            }
            if (isDragging && Input.GetMouseButton(0))
            {
                Vector3 current = Input.mousePosition;
                ApplyScreenDrag(current - previousMousePosition);
                previousMousePosition = current;
            }

            if (Input.GetKey(KeyCode.LeftArrow))
            {
                AddYawDegrees(-keyboardStepDegrees * Time.deltaTime * 60.0f);
            }
            if (Input.GetKey(KeyCode.RightArrow))
            {
                AddYawDegrees(keyboardStepDegrees * Time.deltaTime * 60.0f);
            }
            if (Input.GetKey(KeyCode.UpArrow))
            {
                AddPitchDegrees(keyboardStepDegrees * Time.deltaTime * 60.0f);
            }
            if (Input.GetKey(KeyCode.DownArrow))
            {
                AddPitchDegrees(-keyboardStepDegrees * Time.deltaTime * 60.0f);
            }
            if (Input.GetKey(KeyCode.Q))
            {
                AddRollDegrees(keyboardStepDegrees * Time.deltaTime * 60.0f);
            }
            if (Input.GetKey(KeyCode.E))
            {
                AddRollDegrees(-keyboardStepDegrees * Time.deltaTime * 60.0f);
            }
            if (Input.GetKeyDown(KeyCode.R))
            {
                ResetPose();
            }
        }

        private void ApplyPose()
        {
            ResolveReferences();
            if (lensAnchor == null)
            {
                return;
            }
            lensAnchor.rotation = Quaternion.Euler(pitchDegrees, yawDegrees, rollDegrees);
            if (skyShell != null)
            {
                skyShell.SyncNow();
            }
        }

        private void ResolveReferences()
        {
            if (lensAnchor == null)
            {
                lensAnchor = transform;
            }
            if (skyShell == null)
            {
                skyShell = FindAnyObjectByType<BlackHoleXrSkyShell>();
            }
            if (targetCamera == null)
            {
                targetCamera = Camera.main;
            }
            if (headPoseDriver == null)
            {
                headPoseDriver = FindAnyObjectByType<BlackHoleXrHeadPoseDriver>();
            }
        }

        private static float NormalizeAngle(float value)
        {
            float normalized = Mathf.Repeat(value + 180.0f, 360.0f) - 180.0f;
            return Mathf.Approximately(normalized, -180.0f) ? 180.0f : normalized;
        }
    }
}
