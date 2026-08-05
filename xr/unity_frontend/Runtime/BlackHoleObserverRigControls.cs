using System;
using UnityEngine;

namespace GRBHXR
{
    public sealed class BlackHoleObserverRigControls : MonoBehaviour
    {
        [SerializeField] private Transform trackingOrigin;
        [SerializeField] private Camera targetCamera;
        [SerializeField] private BlackHoleXrHeadPoseDriver headPoseDriver;
        [SerializeField] private BlackHoleRoamKeyframes roamKeyframes;
        [SerializeField] private Transform lensAnchor;
        [SerializeField] private float virtualYawDegrees;
        // Walking is exponential in radius so a stick push feels uniform
        // across two decades of r_obs; angular speeds are constant.
        [SerializeField] private float radialLogSpeedPerSecond = 0.4f;
        [SerializeField] private float angularSpeedDegreesPerSecond = 25.0f;
        [SerializeField] private bool enableDesktopKeys = true;
        [SerializeField] private float virtualRadiusM = -1.0f;
        [SerializeField] private float virtualThetaDeg = -1.0f;
        [SerializeField] private float virtualAzimuthDeg;
        [SerializeField] private float referenceThetaDeg = -1.0f;
        // Free-fall playback: the virtual observer follows the rain-frame
        // radial infall r(tau) with the frame-dragging azimuth drift. This is
        // quasi-static keyframe playback of a free-fall *worldline*; the
        // kinematic aberration/Doppler of the falling frame is the Stage B-2
        // transported-tetrad deliverable and is not modeled here.
        [SerializeField] private bool freeFalling;
        [SerializeField] private float freeFallTauPerSecond = 10.0f;
        private float lastLocomotionWarningTime = -100.0f;

        private bool desktopInputUnavailable;

        public bool FreeFalling => freeFalling;

        public float VirtualYawDegrees => virtualYawDegrees;
        public float VirtualRadiusM => virtualRadiusM > 0.0f
            ? virtualRadiusM
            : (roamKeyframes != null ? roamKeyframes.DefaultRadiusM : -1.0f);
        public float VirtualThetaDeg => virtualThetaDeg > 0.0f
            ? virtualThetaDeg
            : (roamKeyframes != null ? roamKeyframes.StartThetaDeg : 60.0f);
        public float VirtualAzimuthDeg => virtualAzimuthDeg;
        public float ReferenceThetaDeg => referenceThetaDeg > 0.0f ? referenceThetaDeg : VirtualThetaDeg;
        public Transform TrackingOrigin => trackingOrigin;
        public bool RadialLocomotionAvailable => roamKeyframes != null && roamKeyframes.IsReady;

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
            if (!Application.isPlaying)
            {
                return;
            }
            if (freeFalling)
            {
                StepFreeFall(Time.deltaTime);
            }
            if (!enableDesktopKeys || desktopInputUnavailable)
            {
                return;
            }
            try
            {
                float forward = (Input.GetKey(KeyCode.W) ? 1.0f : 0.0f) - (Input.GetKey(KeyCode.S) ? 1.0f : 0.0f);
                float strafe = (Input.GetKey(KeyCode.D) ? 1.0f : 0.0f) - (Input.GetKey(KeyCode.A) ? 1.0f : 0.0f);
                if (forward != 0.0f || strafe != 0.0f)
                {
                    AddWalkInput(new Vector2(strafe, forward), Time.deltaTime);
                }
                float polar = (Input.GetKey(KeyCode.G) ? 1.0f : 0.0f) - (Input.GetKey(KeyCode.T) ? 1.0f : 0.0f);
                if (polar != 0.0f)
                {
                    AddSphericalInput(0.0f, polar, 0.0f, Time.deltaTime);
                }
            }
            catch (InvalidOperationException)
            {
                desktopInputUnavailable = true;
            }
        }

        public void AddYawDegrees(float deltaDegrees)
        {
            ResolveReferences();
            if (trackingOrigin == null || Mathf.Abs(deltaDegrees) < 1.0e-6f)
            {
                return;
            }

            // Rotate tracking space around the current eye position. This changes
            // observer orientation without rotating the lens transfer-map basis or
            // introducing an unmodelled observer translation.
            Vector3 pivot = targetCamera != null
                ? targetCamera.transform.position
                : trackingOrigin.position;
            trackingOrigin.RotateAround(pivot, Vector3.up, deltaDegrees);
            virtualYawDegrees = NormalizeAngle(virtualYawDegrees + deltaDegrees);
        }

        /// <summary>
        /// Walk in the direction the user pushes relative to where they face:
        /// stick y along the head forward axis, stick x along head right. The
        /// world walk vector is decomposed onto the observer's spherical
        /// directions (radial / polar / azimuthal) at the current position.
        /// </summary>
        public void AddWalkInput(Vector2 stick, float deltaTime)
        {
            ResolveReferences();
            if (!RadialLocomotionAvailable || deltaTime <= 0.0f || stick.sqrMagnitude < 1.0e-6f)
            {
                return;
            }
            // Stick input hands control back to the user.
            StopFreeFall();
            EnsurePositionInitialized();

            Transform head = targetCamera != null ? targetCamera.transform : transform;
            Vector3 walkWorld = head.forward * Mathf.Clamp(stick.y, -1.0f, 1.0f)
                + head.right * Mathf.Clamp(stick.x, -1.0f, 1.0f);
            if (walkWorld.sqrMagnitude < 1.0e-8f)
            {
                return;
            }

            Quaternion anchorRotation = lensAnchor != null ? lensAnchor.rotation : Quaternion.identity;
            KerrObserverBasis.SphericalDirections(
                anchorRotation,
                ReferenceThetaDeg,
                roamKeyframes.BoundThetaDeg,
                virtualAzimuthDeg,
                out Vector3 radialOutward,
                out Vector3 polarSouth,
                out Vector3 azimuthPrograde
            );
            AddSphericalInput(
                Vector3.Dot(walkWorld, radialOutward),
                Vector3.Dot(walkWorld, polarSouth),
                Vector3.Dot(walkWorld, azimuthPrograde),
                deltaTime
            );
        }

        /// <summary>Signed spherical walking components in [-1, 1].</summary>
        public void AddSphericalInput(float outward, float south, float prograde, float deltaTime)
        {
            ResolveReferences();
            if (deltaTime <= 0.0f)
            {
                return;
            }
            if (!RadialLocomotionAvailable)
            {
                // Throttled, because this runs from a per-frame stick poll.
                // It used to return in total silence, so "Move inward" did
                // nothing with no diagnostic anywhere.
                if (Time.unscaledTime - lastLocomotionWarningTime > 5.0f)
                {
                    lastLocomotionWarningTime = Time.unscaledTime;
                    Debug.LogWarning(
                        "GR-BH-XR observer locomotion ignored: no roam keyframe grid " +
                        "is bound (missing or unreadable roam_keyframes_metadata.json)."
                    );
                }
                return;
            }
            EnsurePositionInitialized();

            if (Mathf.Abs(outward) > 1.0e-4f)
            {
                float logRadius = Mathf.Log(virtualRadiusM)
                    + Mathf.Clamp(outward, -1.0f, 1.0f) * radialLogSpeedPerSecond * deltaTime;
                virtualRadiusM = roamKeyframes.ClampRadius(Mathf.Exp(logRadius));
            }
            if (Mathf.Abs(south) > 1.0e-4f)
            {
                virtualThetaDeg = roamKeyframes.ClampThetaDeg(
                    virtualThetaDeg + Mathf.Clamp(south, -1.0f, 1.0f) * angularSpeedDegreesPerSecond * deltaTime
                );
            }
            if (Mathf.Abs(prograde) > 1.0e-4f && roamKeyframes.Mode == BlackHoleRoamKeyframes.RoamMode.Grid)
            {
                // Azimuthal motion is exact for any angle: axisymmetry rotates
                // the map basis rigidly about the spin axis. During descent the
                // azimuth follows the falling worldline instead.
                virtualAzimuthDeg = NormalizeAngle(
                    virtualAzimuthDeg + Mathf.Clamp(prograde, -1.0f, 1.0f) * angularSpeedDegreesPerSecond * deltaTime
                );
            }
            if (
                roamKeyframes.Mode == BlackHoleRoamKeyframes.RoamMode.Descent
                && virtualRadiusM >= roamKeyframes.DescentStartRadiusM * 0.999f
            )
            {
                // Climbed back out of the descent sequence: return to the grid.
                roamKeyframes.ExitDescent();
                virtualThetaDeg = roamKeyframes.BoundThetaDeg;
            }
            roamKeyframes.SetTarget(virtualRadiusM, virtualThetaDeg);
        }

        /// <summary>Legacy single-axis radial input (panel buttons).</summary>
        public void AddRadialInput(float stickY, float deltaTime)
        {
            AddSphericalInput(-Mathf.Clamp(stickY, -1.0f, 1.0f), 0.0f, 0.0f, deltaTime);
        }

        /// <summary>
        /// Free fall is only offered when the audited descent keyframes are
        /// bound. Without them the fall would be driven entirely by this
        /// file's Schwarzschild display pacing (see StepFreeFall), which is
        /// not a validated Kerr worldline - so the control is refused rather
        /// than silently run on an unsupported approximation.
        /// </summary>
        public bool FreeFallAvailable
        {
            get
            {
                ResolveReferences();
                return RadialLocomotionAvailable
                    && roamKeyframes != null
                    && roamKeyframes.DescentAvailable;
            }
        }

        public void StartFreeFall()
        {
            ResolveReferences();
            if (!RadialLocomotionAvailable)
            {
                // Used to return silently: the panel button closed the panel
                // and nothing happened, with no log anywhere.
                Debug.LogWarning(
                    "GR-BH-XR free fall unavailable: no roam keyframe grid is bound."
                );
                return;
            }
            if (roamKeyframes == null || !roamKeyframes.DescentAvailable)
            {
                Debug.LogWarning(
                    "GR-BH-XR free fall refused: descent keyframes are not bound. " +
                    "Radial fall would run on this rig's Schwarzschild display pacing " +
                    "(dr/dtau = -sqrt(2M/r), no Kerr correction), which is not a " +
                    "validated observer worldline. Bind Task 8 descent assets first."
                );
                return;
            }
            EnsurePositionInitialized();
            freeFalling = true;
            Debug.Log(
                $"GR-BH-XR free fall started at r={virtualRadiusM:F2}M " +
                "(quasi-static worldline playback, no boost)."
            );
        }

        public void StopFreeFall()
        {
            if (freeFalling)
            {
                freeFalling = false;
                Debug.Log($"GR-BH-XR free fall stopped at r={virtualRadiusM:F2}M.");
            }
        }

        private void StepFreeFall(float deltaTime)
        {
            ResolveReferences();
            if (!RadialLocomotionAvailable)
            {
                freeFalling = false;
                return;
            }
            EnsurePositionInitialized();
            float dtau = deltaTime * freeFallTauPerSecond;
            float radius = Mathf.Max(virtualRadiusM, 0.4f);
            // SCHWARZSCHILD pacing, deliberately labelled as such. This is
            // dr/dtau = -sqrt(2M/r) with M hardcoded to 1, which is the
            // Schwarzschild rain rate. The Kerr equatorial rain rate is
            // dr/dtau = -sqrt(2 M r (r^2 + a^2)) / Sigma, i.e. larger by
            // sqrt(1 + a^2/r^2) on the equator. At a = 0.9 this pacing is
            // slow by 0.40% at 10M, 1.58% at 5M, 5.91% at 2.5M and 8.81% at
            // 2M. It is display pacing for the playback cursor only and is
            // NOT a validated Kerr worldline. The audited rain-frame
            // worldline and its descent keyframes are owned by the Task 7-8
            // physics worktree; when those assets are bound, the keyframe
            // schedule - not this expression - determines the observer state.
            float newRadius = radius - Mathf.Sqrt(2.0f / radius) * dtau;

            if (roamKeyframes.Mode == BlackHoleRoamKeyframes.RoamMode.Grid)
            {
                if (roamKeyframes.DescentAvailable && newRadius <= roamKeyframes.DescentStartRadiusM)
                {
                    // Hand off from the static grid to the descent keyframe
                    // sequence. What the descent assets model is a property of
                    // their producer, which is not on this branch; this rig
                    // only advances the playback cursor into them.
                    roamKeyframes.EnterDescent(virtualThetaDeg, virtualAzimuthDeg);
                    virtualThetaDeg = roamKeyframes.BoundThetaDeg;
                }
                else
                {
                    // Frame-dragging drift while still on static keyframes.
                    //
                    // APPROXIMATE, and the error is not cosmetic: this uses
                    // A = (r^2+a^2)^2 - a^2 Delta (dropping the sin^2(theta)
                    // on the Delta term) and the SCHWARZSCHILD dt/dtau
                    // 1/(1 - 2M/r) instead of the Kerr A/(Delta Sigma). The
                    // resulting dphi/dtau is high by 0.04% at 10M, 0.83% at
                    // 5M, 10.4% at 3M and 33.6% at 2.5M on the equator
                    // (38.0% at theta = 60 deg, r = 2.5M) for a = 0.9 - and
                    // 2.5M is the documented grid floor. virtualAzimuthDeg
                    // feeds _LensWorldRight/Up/Forward, so at the floor the
                    // star field and hole direction rotate at a visibly wrong
                    // rate. Treat this as display pacing, never as a
                    // validated Kerr observer worldline; the audited
                    // worldline is a Task 7-8 physics-worktree deliverable.
                    float spin = roamKeyframes.SpinA;
                    float a2 = spin * spin;
                    float delta = radius * radius - 2.0f * radius + a2;
                    float bigA = (radius * radius + a2) * (radius * radius + a2) - a2 * delta;
                    float omega = 2.0f * spin * radius / Mathf.Max(bigA, 1.0e-4f);
                    float dtDtau = 1.0f / Mathf.Clamp(1.0f - 2.0f / radius, 0.05f, 1.0f);
                    virtualAzimuthDeg = NormalizeAngle(
                        virtualAzimuthDeg + omega * dtDtau * dtau * Mathf.Rad2Deg
                    );
                }
            }
            if (roamKeyframes.Mode == BlackHoleRoamKeyframes.RoamMode.Descent)
            {
                virtualAzimuthDeg = NormalizeAngle(roamKeyframes.DescentAzimuthDeg(newRadius));
            }
            virtualRadiusM = roamKeyframes.ClampRadius(newRadius);
            roamKeyframes.SetTarget(virtualRadiusM, virtualThetaDeg);
            if (virtualRadiusM <= roamKeyframes.MinRadiusM * 1.001f)
            {
                StopFreeFall();
            }
        }

        public void SetAzimuthDegrees(float azimuthDeg)
        {
            EnsurePositionInitialized();
            virtualAzimuthDeg = NormalizeAngle(azimuthDeg);
        }

        public Vector3 TrackingToWorldPoint(Vector3 trackingPoint)
        {
            ResolveReferences();
            return trackingOrigin != null
                ? trackingOrigin.TransformPoint(trackingPoint)
                : trackingPoint;
        }

        public Vector3 TrackingToWorldDirection(Vector3 trackingDirection)
        {
            ResolveReferences();
            return trackingOrigin != null
                ? trackingOrigin.TransformDirection(trackingDirection).normalized
                : trackingDirection.normalized;
        }

        public string StatusText()
        {
            string roam = roamKeyframes != null
                ? roamKeyframes.StatusText()
                : "Roam unavailable: no keyframe grid bound.";
            string mode = "";
            if (freeFalling)
            {
                mode = roamKeyframes != null && roamKeyframes.Mode == BlackHoleRoamKeyframes.RoamMode.Descent
                    ? "  FREE FALL (descent keyframe playback)"
                    : "  FREE FALL (quasi-static segment, no boost)";
            }
            return
                $"Observer yaw {virtualYawDegrees:F1} deg  azimuth {virtualAzimuthDeg:F1} deg{mode}\n" +
                roam;
        }

        private void EnsurePositionInitialized()
        {
            if (virtualRadiusM <= 0.0f && roamKeyframes != null && roamKeyframes.IsReady)
            {
                virtualRadiusM = roamKeyframes.DefaultRadiusM;
            }
            if (virtualThetaDeg <= 0.0f && roamKeyframes != null && roamKeyframes.IsReady)
            {
                virtualThetaDeg = roamKeyframes.StartThetaDeg;
            }
            if (referenceThetaDeg <= 0.0f)
            {
                referenceThetaDeg = virtualThetaDeg > 0.0f ? virtualThetaDeg : 60.0f;
            }
        }

        private void ResolveReferences()
        {
            if (targetCamera == null)
            {
                targetCamera = Camera.main;
            }
            if (headPoseDriver == null && targetCamera != null)
            {
                headPoseDriver = targetCamera.GetComponent<BlackHoleXrHeadPoseDriver>();
            }
            if (trackingOrigin == null && headPoseDriver != null)
            {
                trackingOrigin = headPoseDriver.TrackingOrigin;
            }
            if (trackingOrigin == null)
            {
                trackingOrigin = transform;
            }
            if (headPoseDriver != null && headPoseDriver.TrackingOrigin != trackingOrigin)
            {
                headPoseDriver.SetTrackingOrigin(trackingOrigin);
            }
            if (roamKeyframes == null)
            {
                roamKeyframes = FindAnyObjectByType<BlackHoleRoamKeyframes>();
            }
            if (lensAnchor == null)
            {
                var anchorControls = FindAnyObjectByType<BlackHoleLensAnchorControls>();
                if (anchorControls != null)
                {
                    lensAnchor = anchorControls.transform;
                }
            }
        }

        private static float NormalizeAngle(float value)
        {
            float normalized = Mathf.Repeat(value + 180.0f, 360.0f) - 180.0f;
            return Mathf.Approximately(normalized, -180.0f) ? 180.0f : normalized;
        }
    }
}
