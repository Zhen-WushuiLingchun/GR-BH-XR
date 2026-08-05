using System;
using UnityEngine;

namespace GRBHXR
{
    /// <summary>
    /// MR passthrough source: prefers Meta's supported MRUK
    /// PassthroughCameraAccess path and retains WebCamTexture only as a
    /// diagnostic fallback. Escape directions inside the camera cone sample
    /// the REAL room, so room light runs through the exact bending and
    /// red/blueshift chain; directions outside the cone fall back to the star
    /// field (or black) - the documented one-camera boundary.
    ///
    /// The MRUK backend supplies timestamped camera pose and calibrated
    /// intrinsics through XR_METAX1_passthrough_camera_data. The fallback
    /// still approximates pose with the current head and uses a configurable
    /// FOV. Environment depth acquisition is logged but not yet consumed by
    /// the shader, so the finite-room sphere remains a display approximation.
    /// </summary>
    public sealed class BlackHoleMrPassthrough : MonoBehaviour
    {
        [SerializeField] private Material targetMaterial;
        [SerializeField] private string deviceKeyword = "Quest";
        [SerializeField] private int requestedWidth = 1280;
        [SerializeField] private int requestedHeight = 960;
        [SerializeField] private int requestedFps = 30;
        [SerializeField] private float horizontalFovDeg = 82.0f;
        [SerializeField] private bool preferOfficialMetaCamera = true;
        // 10 s was shorter than a plausible first-frame latency over Link, and
        // the timeout destroyed the supported path mid-gate. 30 s is the gate
        // default; raise it further from the inspector if a device needs it.
        [SerializeField] private float officialBackendTimeoutSeconds = 30.0f;
        // MRUK-only gate mode. When false (the default) the legacy Windows
        // WebCamTexture path is never opened, so a gate run cannot silently
        // leave the supported backend and produce the ambiguous evidence that
        // has cost several sessions. The legacy path also opens the same
        // physical camera, so falling back may poison a later MRUK start
        // within the same session.
        [SerializeField] private bool allowLegacyFallback;
        // Outside the camera cone: 0 = black ("no data"), 1 = star field,
        // 2 = clamp to the frame edge (full-view passthrough feel; the
        // stretch band is a documented display fill, not data).
        [SerializeField] private int fallbackMode = 1;
        [SerializeField] private bool flipVertical;
        [SerializeField] private bool mrEnabled;
        // Finite-room model: the hole gets a room position (along the anchor
        // aim, holeDistance meters from the head) and lensed samples land on
        // a room sphere instead of at infinity. The environment-depth path
        // replaces the sphere once verified on device.
        [SerializeField] private bool finiteRoom = true;
        [SerializeField] private float holeDistanceMeters = 2.0f;
        [SerializeField] private float roomRadiusMeters = 2.5f;

        private WebCamTexture cameraTexture;
        private BlackHoleMrukCameraBridge mrukCamera;
        private GRBHXREnvironmentDepthFeature depthFeature;
        private bool depthLogged;
        private CameraBackend cameraBackend;

        private enum CameraBackend
        {
            None,
            OfficialMetaMruk,
            LegacyWebCam,
        }

        // Camera bring-up state machine: the Meta virtual camera may open
        // without delivering frames (width stays at the 16-px placeholder),
        // so each (device x mode) attempt gets a timeout before the next is
        // tried. Every transition logs - black screens must leave evidence.
        private string[] candidateDevices = new string[0];
        private int attemptIndex = -1;
        private float attemptStartTime;
        private bool frameLocked;
        private float lastWaitingLineTime = -100.0f;
        private string lastResolutionText = "-";

        /// <summary>
        /// OpenXR extension that carries passthrough camera data. The last
        /// device probe recorded it as AVAILABLE but NOT ENABLED, and nothing
        /// in this repository enables it, so the distinction has to reach the
        /// log rather than only the JSON artifact.
        /// </summary>
        public const string CameraExtensionName = "XR_METAX1_passthrough_camera_data";

        /// <summary>
        /// "enabled", "available", or "absent" for the camera extension.
        /// Wrapped because OpenXRRuntime throws when no XR loader is active
        /// (editor play without a headset), and a diagnostic must never be
        /// the thing that breaks the run it is diagnosing.
        /// </summary>
        public static string CameraExtensionStateText()
        {
            try
            {
                if (UnityEngine.XR.OpenXR.OpenXRRuntime.IsExtensionEnabled(CameraExtensionName))
                {
                    return "enabled";
                }
                foreach (string name in UnityEngine.XR.OpenXR.OpenXRRuntime.GetAvailableExtensions())
                {
                    if (name == CameraExtensionName)
                    {
                        return "available";
                    }
                }
                return "absent";
            }
            catch (Exception)
            {
                return "unknown";
            }
        }
        private static readonly Vector3Int[] AttemptModes =
        {
            new Vector3Int(0, 0, 0),        // device default
            new Vector3Int(1280, 960, 30),
            new Vector3Int(640, 480, 30),
        };

        public bool MrEnabled => mrEnabled;

        public static bool ProbeOfficialCameraBackend(out string reason)
        {
            return BlackHoleMrukCameraBridge.IsAvailable(out reason);
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Bootstrap()
        {
            if (Application.isPlaying)
            {
                Ensure();
            }
        }

        /// <summary>Find-or-create. The host must NOT carry
        /// HideFlags.DontSave: FindAnyObjectByType skips DontSave objects,
        /// which silently disconnected the settings-panel button.</summary>
        public static BlackHoleMrPassthrough Ensure()
        {
            var existing = FindAnyObjectByType<BlackHoleMrPassthrough>();
            if (existing != null)
            {
                return existing;
            }
            var host = new GameObject("BlackHoleMrPassthrough");
            DontDestroyOnLoad(host);
            return host.AddComponent<BlackHoleMrPassthrough>();
        }

        public void ToggleMr()
        {
            SetMr(!mrEnabled);
        }

        public void SetMr(bool enabledValue)
        {
            ResolveMaterial();
            if (enabledValue)
            {
                // Kick the runtime passthrough session first: the Link camera
                // pipeline may gate frame delivery on it.
                depthFeature = depthFeature != null ? depthFeature : GRBHXREnvironmentDepthFeature.Instance;
                if (depthFeature != null && depthFeature.enabled)
                {
                    depthFeature.EnsurePassthroughStarted();
                }
                // Record enabled-vs-available once per MR enable. Without
                // this the operator has to retrieve xr_capability_probe.json
                // from persistentDataPath to learn the single most decisive
                // fact about the session.
                Debug.Log(
                    $"GR-BH-XR MR: {CameraExtensionName} is {CameraExtensionStateText()}; " +
                    $"MRUK type route={BlackHoleMrukCameraBridge.ResolvedVia}."
                );
                if (cameraBackend == CameraBackend.None && !TryStartPreferredCamera())
                {
                    Debug.LogWarning(
                        "GR-BH-XR MR: no passthrough camera backend could start. " +
                        "Install Meta MRUK for the supported camera path and verify the Link camera toggle."
                    );
                    enabledValue = false;
                }
            }
            else
            {
                StopCamera();
                attemptIndex = -1;
                frameLocked = false;
                cameraBackend = CameraBackend.None;
            }
            mrEnabled = enabledValue;
            if (targetMaterial != null)
            {
                targetMaterial.SetFloat("_UseMrPassthrough", mrEnabled ? 1.0f : 0.0f);
            }
            // The GRBHXR_ROAM_BLEND shader variant compiles out _MrCameraTex
            // and sampleBackground entirely to stay inside the 16-sampler
            // budget, and BlackHoleRoamKeyframes enables that keyword for
            // essentially all of roam playback. Turning MR on there starts the
            // camera and sets _UseMrPassthrough but changes no pixel, and the
            // operator saw only a confident "ON". Say what is actually true.
            //
            // The shader-side fix (moving the sampler out of the #ifndef,
            // measured to fit at 16/16) is deliberately NOT applied here: it
            // cannot be verified without a Unity shader compile, and getting
            // the sampler budget wrong takes down the whole renderer. Recorded
            // as a follow-up requiring an editor compile.
            bool roamBlendActive = mrEnabled
                && targetMaterial != null
                && targetMaterial.IsKeywordEnabled("GRBHXR_ROAM_BLEND");
            if (roamBlendActive)
            {
                Debug.LogWarning(
                    "GR-BH-XR MR passthrough ON but INERT: the GRBHXR_ROAM_BLEND " +
                    "shader variant is active and compiles out the MR camera " +
                    "sampler, so room pixels cannot reach the lens shader. " +
                    "Disable roam keyframe blending (enable live tracing) to test MR."
                );
            }
            else
            {
                Debug.Log($"GR-BH-XR MR passthrough {(mrEnabled ? "ON" : "OFF")}.");
            }
        }

        public string StatusText()
        {
            if (!mrEnabled)
            {
                return "MR passthrough OFF.";
            }
            if (cameraBackend == CameraBackend.None)
            {
                return "MR passthrough: no camera.";
            }
            if (cameraBackend == CameraBackend.OfficialMetaMruk)
            {
                // Compact enough to read in-headset. Everything here is what
                // an operator needs to tell "delivering" from "allocated":
                // the delivered-frame count, the negotiated resolution, and
                // whether the camera OpenXR extension is enabled or merely
                // available.
                int stamps = mrukCamera != null ? mrukCamera.DistinctTimestamps : 0;
                string ext = CameraExtensionStateText();
                if (frameLocked)
                {
                    float age = mrukCamera != null ? mrukCamera.DeliveryAgeSeconds : -1.0f;
                    string freshness = mrukCamera != null && mrukCamera.IsStreamStale
                        ? $"STALE {age:F1}s"
                        : $"age {age:F2}s";
                    return $"MRUK feed  n={stamps}  {freshness}  {lastResolutionText}  ext={ext}";
                }
                return
                    $"MRUK waiting  n={stamps}/{BlackHoleMrukCameraBridge.RequiredDistinctTimestamps}" +
                    $"  ext={ext}  ({mrukCamera?.LastError})";
            }
            return $"MR passthrough: LEGACY {cameraTexture?.deviceName} {cameraTexture?.width}x{cameraTexture?.height}.";
        }

        private bool TryStartPreferredCamera()
        {
            string availability = "not probed";
            if (preferOfficialMetaCamera && BlackHoleMrukCameraBridge.IsAvailable(out availability))
            {
                mrukCamera = new BlackHoleMrukCameraBridge();
                if (mrukCamera.Start(transform, requestedWidth, requestedHeight, requestedFps))
                {
                    cameraBackend = CameraBackend.OfficialMetaMruk;
                    attemptStartTime = Time.realtimeSinceStartup;
                    frameLocked = false;
                    Debug.Log($"GR-BH-XR MR: starting supported Meta camera backend ({availability}).");
                    return true;
                }
                Debug.LogWarning(
                    $"GR-BH-XR MR: Meta camera backend failed to start ({mrukCamera.LastError}); " +
                    "trying the legacy WebCamTexture diagnostic fallback."
                );
                mrukCamera.Stop();
                mrukCamera = null;
            }
            else if (preferOfficialMetaCamera)
            {
                Debug.LogWarning(
                    $"GR-BH-XR MR: supported Meta camera backend unavailable ({availability}); " +
                    "the WebCamTexture route is a legacy diagnostic fallback, not the production path."
                );
            }

            if (!allowLegacyFallback)
            {
                Debug.LogWarning(
                    "GR-BH-XR MR: MRUK-only mode; the legacy WebCamTexture fallback is " +
                    "disabled. Set allowLegacyFallback to use the diagnostic path."
                );
                return false;
            }
            return TryStartLegacyCamera();
        }

        /// <summary>
        /// Corroborating device evidence for the acceptance record.
        ///
        /// This exists because a ticking timestamp is NOT sufficient on its
        /// own. MRUK leaves MrukConfig.disablePcaMockFallback at its default
        /// false and ships a mock camera backend, and the package exposes no
        /// supported way for an application to disable that fallback before
        /// native context creation. A mock feed would satisfy IsPlaying, a
        /// non-null texture, parseable intrinsics AND advancing timestamps.
        /// So the gate record also carries the active OpenXR runtime and the
        /// reported headset type, and the caller additionally logs the lens
        /// offset via DescribeCalibration. None of this makes the acceptance
        /// string proof of device-verified RGB by itself: a real device log
        /// showing the OpenXR camera backend opening is still required.
        ///
        /// OVRPlugin is reached by reflection so the package keeps no
        /// compile-time dependency on Meta assemblies.
        /// </summary>
        public static string DeviceEvidenceText()
        {
            string runtime;
            try
            {
                runtime = $"{UnityEngine.XR.OpenXR.OpenXRRuntime.name} {UnityEngine.XR.OpenXR.OpenXRRuntime.version}";
            }
            catch (Exception)
            {
                runtime = "unavailable";
            }

            string headset = "unknown";
            try
            {
                Type ovrPlugin = null;
                foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
                {
                    ovrPlugin = assembly.GetType("OVRPlugin", false);
                    if (ovrPlugin != null)
                    {
                        break;
                    }
                }
                var method = ovrPlugin?.GetMethod(
                    "GetSystemHeadsetType",
                    System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.Public
                );
                object value = method?.Invoke(null, null);
                headset = value != null ? value.ToString() : "OVRPlugin absent";
            }
            catch (Exception ex)
            {
                headset = $"query failed: {ex.GetType().Name}";
            }

            return
                $"evidence: openXrRuntime=\"{runtime}\" headsetType={headset} " +
                $"cameraExtension={CameraExtensionStateText()} " +
                "mockFallback=NOT-DISABLEABLE(MRUK default) " +
                "deviceVerified=NO(requires a real device log showing the OpenXR camera backend opened)";
        }

        /// <summary>
        /// 1 Hz throttle so a stalled bring-up leaves continuous evidence in
        /// Player.log without flooding it at frame rate.
        /// </summary>
        private void ThrottledWaitingLine(string message)
        {
            if (Time.realtimeSinceStartup - lastWaitingLineTime < 1.0f)
            {
                return;
            }
            lastWaitingLineTime = Time.realtimeSinceStartup;
            Debug.Log(message);
        }

        private bool TryStartLegacyCamera()
        {
            WebCamDevice[] devices = WebCamTexture.devices;
            var matches = new System.Collections.Generic.List<string>();
            foreach (WebCamDevice device in devices)
            {
                if (device.name.IndexOf(deviceKeyword, StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    matches.Add(device.name);
                }
            }
            if (matches.Count == 0)
            {
                Debug.LogWarning(
                    "GR-BH-XR MR: no camera matches '" + deviceKeyword + "'. Devices: "
                    + string.Join(", ", Array.ConvertAll(devices, device => device.name))
                );
                return false;
            }
            candidateDevices = matches.ToArray();
            frameLocked = false;
            cameraBackend = CameraBackend.LegacyWebCam;
            StartAttempt(0);
            return true;
        }

        private void StartAttempt(int index)
        {
            StopCamera();
            cameraBackend = CameraBackend.LegacyWebCam;
            attemptIndex = index;
            attemptStartTime = Time.realtimeSinceStartup;
            string deviceName = candidateDevices[index / AttemptModes.Length];
            Vector3Int mode = AttemptModes[index % AttemptModes.Length];
            cameraTexture = mode.x > 0
                ? new WebCamTexture(deviceName, mode.x, mode.y, mode.z)
                : new WebCamTexture(deviceName);
            cameraTexture.Play();
            Debug.Log(
                $"GR-BH-XR MR: camera attempt {index + 1}/{candidateDevices.Length * AttemptModes.Length}: " +
                $"'{deviceName}' mode={(mode.x > 0 ? $"{mode.x}x{mode.y}@{mode.z}" : "default")}."
            );
        }

        /// <summary>Advance the attempt ladder until frames actually arrive
        /// (the placeholder texture stays 16 px until then).</summary>
        private void UpdateCameraBringUp()
        {
            if (cameraBackend == CameraBackend.OfficialMetaMruk)
            {
                if (mrukCamera != null && mrukCamera.TryGetFrame(out BlackHoleMrukCameraBridge.Frame frame))
                {
                    // ACCEPTANCE. Gated on HasEverUpdated, which latches only
                    // when MRUK's own Timestamp advances. A session that is
                    // playing with an allocated-but-never-updated texture at
                    // the requested resolution reproduces the exact failure
                    // class of the 16-px WebCamTexture placeholder, and this
                    // string is treated as *the* Task 10 criterion in five
                    // documents - so it must not fire on an allocation.
                    lastResolutionText = $"{frame.resolution.x}x{frame.resolution.y}";
                    if (!frameLocked && mrukCamera.HasDeliveredStream)
                    {
                        frameLocked = true;
                        Debug.Log(
                            $"GR-BH-XR MR: Meta MRUK delivering calibrated " +
                            $"{frame.resolution.x}x{frame.resolution.y} camera frames " +
                            $"(distinctTimestamps={mrukCamera.DistinctTimestamps}). " +
                            mrukCamera.DescribeCalibration() + " " + DeviceEvidenceText()
                        );
                    }
                    else if (!frameLocked)
                    {
                        // Deliberately DIFFERENT, weaker strings, so playing /
                        // one-fill / streaming are separable in Player.log.
                        ThrottledWaitingLine(
                            "GR-BH-XR MR: Meta MRUK session playing, awaiting a delivered stream " +
                            $"({frame.resolution.x}x{frame.resolution.y}, distinctTimestamps=" +
                            $"{mrukCamera.DistinctTimestamps}/{BlackHoleMrukCameraBridge.RequiredDistinctTimestamps})."
                        );
                    }
                    else if (mrukCamera.IsStreamStale)
                    {
                        // Accepted, then delivery stopped. This must be visible:
                        // the texture stays bound and the image simply freezes,
                        // which looks like a working feed in a screenshot.
                        ThrottledWaitingLine(
                            "GR-BH-XR MR: STALE MRUK stream - no new timestamp for " +
                            $"{mrukCamera.DeliveryAgeSeconds:F1}s " +
                            $"(accepted after {mrukCamera.DistinctTimestamps} timestamps). " +
                            "Any capture taken now shows a frozen frame."
                        );
                    }
                    return;
                }

                if (Time.realtimeSinceStartup - attemptStartTime < officialBackendTimeoutSeconds)
                {
                    // A stalled session used to leave exactly one message, at
                    // timeout. Emit LastError continuously instead.
                    ThrottledWaitingLine(
                        "GR-BH-XR MR: waiting for Meta MRUK first frame " +
                        $"({(mrukCamera != null ? mrukCamera.LastError : "bridge missing")})."
                    );
                    return;
                }

                string reason = mrukCamera != null ? mrukCamera.LastError : "bridge missing";
                if (!allowLegacyFallback)
                {
                    // MRUK-only: keep the supported backend alive and keep
                    // waiting rather than destroying it and producing
                    // ambiguous legacy evidence.
                    ThrottledWaitingLine(
                        $"GR-BH-XR MR: Meta MRUK delivered no updated frame within " +
                        $"{officialBackendTimeoutSeconds:F1}s ({reason}). MRUK-only mode: " +
                        "the legacy WebCamTexture fallback is disabled, still waiting."
                    );
                    return;
                }
                Debug.LogWarning(
                    $"GR-BH-XR MR: Meta MRUK delivered no frame within " +
                    $"{officialBackendTimeoutSeconds:F1}s ({reason}); trying legacy WebCamTexture."
                );
                mrukCamera?.Stop();
                mrukCamera = null;
                cameraBackend = CameraBackend.None;
                if (!TryStartLegacyCamera())
                {
                    attemptIndex = -1;
                }
                return;
            }

            if (frameLocked || cameraBackend != CameraBackend.LegacyWebCam || cameraTexture == null || attemptIndex < 0)
            {
                return;
            }
            if (cameraTexture.didUpdateThisFrame && cameraTexture.width > 16)
            {
                frameLocked = true;
                Debug.Log(
                    $"GR-BH-XR MR: camera '{cameraTexture.deviceName}' delivering " +
                    $"{cameraTexture.width}x{cameraTexture.height} " +
                    $"(mirrored={cameraTexture.videoVerticallyMirrored}, rotation={cameraTexture.videoRotationAngle})."
                );
                return;
            }
            if (Time.realtimeSinceStartup - attemptStartTime < 4.0f)
            {
                return;
            }
            int next = attemptIndex + 1;
            if (next < candidateDevices.Length * AttemptModes.Length)
            {
                StartAttempt(next);
            }
            else
            {
                Debug.LogWarning(
                    "GR-BH-XR MR: no camera attempt delivered frames. The Link 'Passthrough Camera API' " +
                    "toggle, Windows camera privacy settings, and headset passthrough state are the suspects. " +
                    $"Passthrough session: {(depthFeature != null ? depthFeature.PassthroughStatus : "no feature")}."
                );
                attemptIndex = -1;
            }
        }

        private void StopCamera()
        {
            if (mrukCamera != null)
            {
                mrukCamera.Stop();
                mrukCamera = null;
            }
            if (cameraTexture != null)
            {
                cameraTexture.Stop();
                Destroy(cameraTexture);
                cameraTexture = null;
            }
            cameraBackend = CameraBackend.None;
        }

        private void Update()
        {
            if (!mrEnabled || cameraBackend == CameraBackend.None)
            {
                return;
            }
            // Bring-up diagnostics run BEFORE the material guard. Previously a
            // scene without the sky shell (the only thing ResolveMaterial can
            // find a material through) logged "MR ON" and then produced no
            // further output at all - the same silent signature that has cost
            // a debugging round before.
            UpdateCameraBringUp();
            if (targetMaterial == null)
            {
                return;
            }

            Camera head = Camera.main;
            if (head == null)
            {
                return;
            }
            Pose cameraPose;
            Texture sourceTexture;
            Vector4 projection;
            bool vFlip;
            if (cameraBackend == CameraBackend.OfficialMetaMruk)
            {
                if (mrukCamera == null || !mrukCamera.TryGetFrame(out BlackHoleMrukCameraBridge.Frame frame))
                {
                    return;
                }
                cameraPose = frame.pose;
                sourceTexture = frame.texture;
                projection = frame.projection;
                vFlip = flipVertical;
            }
            else
            {
                if (cameraTexture == null || !frameLocked)
                {
                    return;
                }
                Transform headPose = head.transform;
                cameraPose = new Pose(headPose.position, headPose.rotation);
                sourceTexture = cameraTexture;
                float tanHalfX = Mathf.Tan(0.5f * horizontalFovDeg * Mathf.Deg2Rad);
                float aspect = (float)cameraTexture.height / cameraTexture.width;
                float tanHalfY = tanHalfX * aspect;
                projection = new Vector4(
                    0.5f / Mathf.Max(tanHalfX, 1.0e-4f),
                    0.5f / Mathf.Max(tanHalfY, 1.0e-4f),
                    0.5f,
                    0.5f
                );
                vFlip = flipVertical ^ cameraTexture.videoVerticallyMirrored;
            }

            targetMaterial.SetTexture("_MrCameraTex", sourceTexture);
            targetMaterial.SetVector("_MrCamRight", cameraPose.rotation * Vector3.right);
            targetMaterial.SetVector("_MrCamUp", cameraPose.rotation * Vector3.up);
            targetMaterial.SetVector("_MrCamForward", cameraPose.rotation * Vector3.forward);
            targetMaterial.SetVector("_MrCamProjection", projection);
            targetMaterial.SetVector(
                "_MrCamParams",
                new Vector4(0.0f, 0.0f, vFlip ? 1.0f : 0.0f, (float)fallbackMode)
            );

            // Finite-room model: hole position relative to the head, along
            // the anchor aim direction.
            var anchor = FindAnyObjectByType<BlackHoleLensAnchorControls>();
            Vector3 holeDirection = anchor != null
                ? anchor.transform.rotation * Vector3.forward
                : cameraPose.rotation * Vector3.forward;
            targetMaterial.SetVector(
                "_MrFinite",
                new Vector4(finiteRoom ? 1.0f : 0.0f, Mathf.Max(roomRadiusMeters, 0.5f), 0.0f, 0.0f)
            );
            targetMaterial.SetVector("_MrHolePosRel", holeDirection * holeDistanceMeters);

            // Structured-light depth bring-up: acquire and LOG (shader use is
            // enabled only after the swapchain wrap is verified on device).
            if (depthFeature == null)
            {
                depthFeature = GRBHXREnvironmentDepthFeature.Instance;
            }
            if (depthFeature != null && depthFeature.enabled)
            {
                bool acquired = depthFeature.TryAcquire(
                    out Texture2D depthTexture,
                    out GRBHXREnvironmentDepthFeature.ImageView leftView,
                    out float nearZ,
                    out float farZ
                );
                if (acquired && !depthLogged)
                {
                    depthLogged = true;
                    Debug.Log(
                        $"GR-BH-XR depth: first acquire OK {depthFeature.Width}x{depthFeature.Height}, " +
                        $"near={nearZ:F3} far={farZ:F1}, fovL={leftView.fov.angleLeft:F3}/{leftView.fov.angleRight:F3}, " +
                        $"texture={(depthTexture != null ? "wrapped" : "null")}."
                    );
                }
            }
        }

        private void OnDestroy()
        {
            StopCamera();
        }

        private void ResolveMaterial()
        {
            if (targetMaterial != null)
            {
                return;
            }
            var shell = FindAnyObjectByType<BlackHoleXrSkyShell>();
            if (shell != null)
            {
                var shellRenderer = shell.GetComponent<Renderer>();
                if (shellRenderer != null)
                {
                    targetMaterial = shellRenderer.sharedMaterial;
                }
            }
        }
    }
}
