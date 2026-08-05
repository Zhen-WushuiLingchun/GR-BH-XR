using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using UnityEngine;

namespace GRBHXR
{
    [Serializable]
    public sealed class RoamMetric
    {
        public float M = 1.0f;
        public float a;
    }

    [Serializable]
    public sealed class RoamKeyframesManifest
    {
        public string schema;
        public int faceSize;
        public RoamMetric metric;
        public float[] radiiM;
        public float[] thetaDegrees;
        public string[] keyframeDirs;
        public float[] skyBlueshiftPerKeyframe;
        public string locomotionNote;
    }

    [Serializable]
    public sealed class DescentKeyframeEntry
    {
        public string dir;
        public int thetaIndex;
        public int radiusIndex;
        public float theta_deg;
        public float r_obs;
        public float azimuthDeg;
        public float[] eInf;
    }

    [Serializable]
    public sealed class DescentManifest
    {
        public string schema;
        public int faceSize;
        public RoamMetric metric;
        public float[] thetaDegrees;
        public float[] radiiM;
        public string[] keyframeDirs;
        public DescentKeyframeEntry[] keyframes;
    }

    /// <summary>
    /// Quasi-static roam playback over an (r, theta) grid of static-observer
    /// keyframes.
    ///
    /// A rain-frame descent sequence (past-directed Kerr-Schild tracing
    /// through the outer horizon) is supported as an asset format, but its
    /// producer lives in the Task 7-8 physics worktree and is not present on
    /// this branch. This file makes no claim about the correctness of descent
    /// physics; when the assets are absent the descent path is inert and says
    /// so.
    ///
    /// Motion between grid radii is NOT solved: the shader dissolves the two
    /// final RGB images of the keyframes bracketing the virtual radius
    /// (GRBHXR_ROAM_BLEND). Polar-angle motion snaps to the nearest traced
    /// row with no interpolation at all. Azimuth is the one exact case - Kerr
    /// axisymmetry makes it a rigid rotation of the cached solution about the
    /// spin axis, requiring no new tracing.
    /// </summary>
    public sealed class BlackHoleRoamKeyframes : MonoBehaviour
    {
        public const string SupportedSchema = "gr-bh-xr.task7.roam_keyframes.v2";
        public const string SupportedDescentSchema = "gr-bh-xr.task8.descent_keyframes.v1";

        public enum RoamMode
        {
            Grid,
            Descent
        }

        private enum KeyframeState
        {
            Unloaded,
            LoadingBytes,
            Ready
        }

        private sealed class Keyframe
        {
            public KeyframeState State = KeyframeState.Unloaded;
            public Task<byte[][]> BytesTask;
            public Cubemap EventCube;
            public Cubemap EscapeDirCube;
            public Cubemap DiskOrder0Cube;
            public Cubemap DiskOrder1Cube;
            public Cubemap DiskOrder0RedshiftCube;
            public Cubemap DiskOrder1RedshiftCube;
        }

        private static readonly string[] KeyframeFileNames =
        {
            "event_cube_rgba8.bytes",
            "escape_dir_unity_cube_rgba32f.bytes",
            "disk_order0_transfer_cube_rgba16f.bytes",
            "disk_order1_transfer_cube_rgba16f.bytes",
            "disk_order0_redshift_cube_rgba16f.bytes",
            "disk_order1_redshift_cube_rgba16f.bytes",
        };

        private static readonly string[] SetASlots =
        {
            "_EventCube", "_EscapeDirCube", "_DiskOrder0Cube", "_DiskOrder1Cube",
            "_DiskOrder0RedshiftCube", "_DiskOrder1RedshiftCube",
        };

        private static readonly string[] SetBSlots =
        {
            "_EventCubeB", "_EscapeDirCubeB", "_DiskOrder0CubeB", "_DiskOrder1CubeB",
            "_DiskOrder0RedshiftCubeB", "_DiskOrder1RedshiftCubeB",
        };

        [SerializeField] private Material targetMaterial;
        [SerializeField] private string manifestRelativePath = "GRBHXR_Roam/roam_keyframes_metadata.json";
        [SerializeField] private string descentManifestRelativePath = "GRBHXR_Descent/descent_keyframes_metadata.json";
        [SerializeField] private bool bindStartKeyframeOnStart = true;
        [SerializeField] private float startThetaDeg = 60.0f;

        private RoamKeyframesManifest manifest;
        private DescentManifest descentManifest;
        private Keyframe[] keyframes;
        private Keyframe[] descentKeyframes;
        private float[] logRadii;
        private float[] descentLogRadii;
        private RoamMode mode = RoamMode.Grid;
        private int descentThetaIndex;
        // INGOING KERR-SCHILD, not BL. The static grid hands off a BL label;
        // EnterDescent converts it once so this can be added to the manifest's
        // per-keyframe azimuthDeg (also KS) without mixing charts.
        private float descentHandoffAzimuthKsDeg;
        private float targetRadius = -1.0f;
        private float targetThetaDeg = -1.0f;
        private int boundIndexA = -1;
        private int boundIndexB = -1;
        private bool boundSetIsDescent;
        private float roamBlend;
        private string loadError;

        public bool IsReady => manifest != null && keyframes != null && manifest.radiiM.Length >= 2;
        public bool DescentAvailable => descentManifest != null && descentKeyframes != null;
        public RoamMode Mode => mode;
        public float DefaultRadiusM => IsReady ? manifest.radiiM[0] : -1.0f;
        public float MinRadiusM => mode == RoamMode.Descent && DescentAvailable
            ? descentManifest.radiiM[descentManifest.radiiM.Length - 1]
            : (IsReady ? manifest.radiiM[manifest.radiiM.Length - 1] : -1.0f);
        public float DescentStartRadiusM => DescentAvailable ? descentManifest.radiiM[0] : -1.0f;
        public float StartThetaDeg => IsReady ? manifest.thetaDegrees[NearestIndex(manifest.thetaDegrees, startThetaDeg)] : startThetaDeg;
        public float SpinA => IsReady && manifest.metric != null ? manifest.metric.a : 0.9f;
        /// <summary>
        /// Metric the BOUND asset set was generated under, geometric units.
        /// Descent playback reads the descent manifest, grid roam the grid
        /// manifest; a scene that binds both with different metrics is
        /// rejected at load (<see cref="MetricsAgree"/>).
        /// </summary>
        public float MetricMassM => mode == RoamMode.Descent && DescentAvailable && descentManifest.metric != null
            ? descentManifest.metric.M
            : (IsReady && manifest.metric != null ? manifest.metric.M : 1.0f);
        public float MetricSpinA => mode == RoamMode.Descent && DescentAvailable && descentManifest.metric != null
            ? descentManifest.metric.a
            : SpinA;
        public bool HasGridMetric => IsReady && manifest.metric != null;
        public bool HasDescentMetric => DescentAvailable && descentManifest.metric != null;
        public float DescentMetricMassM => HasDescentMetric ? descentManifest.metric.M : float.NaN;
        public float DescentMetricSpinA => HasDescentMetric ? descentManifest.metric.a : float.NaN;
        public float GridMetricMassM => HasGridMetric ? manifest.metric.M : float.NaN;
        public float GridMetricSpinA => HasGridMetric ? manifest.metric.a : float.NaN;
        public float BoundThetaDeg => CurrentThetaDeg();
        public RoamKeyframesManifest Manifest => manifest;

        private void Awake()
        {
            LoadManifest();
        }

        private void Start()
        {
            if (Application.isPlaying && IsReady && bindStartKeyframeOnStart)
            {
                targetRadius = DefaultRadiusM;
                targetThetaDeg = StartThetaDeg;
            }
        }

        private void Update()
        {
            if (!Application.isPlaying || !IsReady)
            {
                return;
            }
            UpdateBinding();
        }

        private void OnDestroy()
        {
            ReleaseAll(keyframes);
            ReleaseAll(descentKeyframes);
        }

        public void LoadManifest()
        {
            if (manifest == null)
            {
                manifest = ParseGridManifest(out keyframes, out logRadii);
            }
            if (descentManifest == null)
            {
                descentManifest = ParseDescentManifest(out descentKeyframes, out descentLogRadii);
            }
        }

        public float ClampRadius(float radius)
        {
            if (!IsReady)
            {
                return radius;
            }
            float[] radii = ActiveRadii();
            float clamped = Mathf.Clamp(radius, radii[radii.Length - 1], radii[0]);
            // Load throttle: do not move past an unloaded bracketing keyframe.
            int outer = OuterIndex(clamped);
            Keyframe[] cache = ActiveCache();
            int flatOuter = FlatIndex(outer);
            int flatInner = FlatIndex(Mathf.Min(outer + 1, radii.Length - 1));
            if (cache[flatInner].State != KeyframeState.Ready)
            {
                clamped = Mathf.Max(clamped, radii[Mathf.Min(outer + 1, radii.Length - 1)]);
            }
            if (cache[flatOuter].State != KeyframeState.Ready && outer > 0)
            {
                clamped = Mathf.Min(clamped, radii[outer]);
            }
            return clamped;
        }

        public float ClampThetaDeg(float thetaDeg)
        {
            if (!IsReady || mode == RoamMode.Descent)
            {
                return CurrentThetaDeg();
            }
            return Mathf.Clamp(thetaDeg, manifest.thetaDegrees[0], manifest.thetaDegrees[manifest.thetaDegrees.Length - 1]);
        }

        public void SetTarget(float radius, float thetaDeg)
        {
            if (!IsReady)
            {
                return;
            }
            targetRadius = ClampRadius(radius);
            targetThetaDeg = ClampThetaDeg(thetaDeg);
        }

        /// <summary>
        /// Hand off from the BL-labelled static grid into the descent set.
        /// `handoffAzimuthBlDeg` is a Boyer-Lindquist label (the grid's chart);
        /// the descent manifest's per-keyframe `azimuthDeg` is ingoing
        /// Kerr-Schild and is measured relative to the FIRST descent keyframe,
        /// whose worldline starts at BL `phi = 0`. So the KS azimuth along the
        /// descent is
        ///
        ///     phi_ks(r_i) = handoffBL + shift(r_start) + azimuthDeg[i]
        ///
        /// and the `shift(r_start)` term is converted exactly once, here.
        /// </summary>
        public bool EnterDescent(float thetaDeg, float handoffAzimuthBlDeg)
        {
            if (!DescentAvailable)
            {
                return false;
            }
            descentThetaIndex = NearestIndex(descentManifest.thetaDegrees, thetaDeg);
            mode = RoamMode.Descent;
            descentHandoffAzimuthKsDeg = handoffAzimuthBlDeg
                + KerrObserverBasis.BlToKsPhiShiftDeg(MetricMassM, MetricSpinA, DescentStartRadiusM);
            targetRadius = Mathf.Min(targetRadius > 0.0f ? targetRadius : DescentStartRadiusM, DescentStartRadiusM);
            Debug.Log(
                $"GR-BH-XR descent entered: theta row {descentManifest.thetaDegrees[descentThetaIndex]:F0} deg, " +
                $"handoff azimuth {handoffAzimuthBlDeg:F1} deg [BL] = " +
                $"{descentHandoffAzimuthKsDeg:F1} deg [KS] at r_start={DescentStartRadiusM:F3}M " +
                $"(M={MetricMassM:F3}, a={MetricSpinA:F4})."
            );
            return true;
        }

        public void ExitDescent()
        {
            if (mode != RoamMode.Descent)
            {
                return;
            }
            mode = RoamMode.Grid;
            targetRadius = Mathf.Max(targetRadius, manifest.radiiM[manifest.radiiM.Length - 1]);
            Debug.Log("GR-BH-XR descent exited to the static grid.");
        }

        /// <summary>
        /// Descent worldline azimuth at the given radius, in the INGOING
        /// KERR-SCHILD chart (deg) - the chart the accepted Task 8 manifest
        /// publishes. Consumers that need a Kerr-Schild Cartesian position
        /// must NOT apply `bl_to_ks_phi_shift` to this value.
        /// </summary>
        public float DescentAzimuthKsDeg(float radius)
        {
            if (!DescentAvailable)
            {
                return 0.0f;
            }
            float[] radii = descentManifest.radiiM;
            int row = descentThetaIndex;
            int outer = OuterIndexIn(radii, radius);
            int inner = Mathf.Min(outer + 1, radii.Length - 1);
            float azOuter = descentManifest.keyframes[row * radii.Length + outer].azimuthDeg;
            float azInner = descentManifest.keyframes[row * radii.Length + inner].azimuthDeg;
            float weight = LogWeight(radii[outer], radii[inner], radius);
            return descentHandoffAzimuthKsDeg + Mathf.Lerp(azOuter, azInner, weight);
        }

        /// <summary>
        /// Blend state consumed by the basis writer (LensMap).
        ///
        /// CHART: `azimuthDegA/B` are BOYER-LINDQUIST LABELS in both modes.
        /// The display basis and `_DiskObserverAzimuth` both live in the BH
        /// Cartesian frame, whose azimuth is `phi_bl` (BH Cartesian is the KS
        /// Cartesian frame rotated by `-(atan2(a, r) + shift)`), and the
        /// traced `phi_m` recorded in the disk channels is likewise BL. The
        /// descent manifest stores KS, so it is converted per keyframe here,
        /// at that keyframe's own radius. Inside the outer horizon the BL
        /// label is a formal continuation and is used only as a continuous
        /// display label, never as a BL coordinate.
        /// </summary>
        public bool TryGetBlendState(
            out float thetaDegA, out float azimuthDegA, out Vector4 eInfA,
            out float thetaDegB, out float azimuthDegB, out Vector4 eInfB,
            out float blend, out bool blendActive)
        {
            thetaDegA = CurrentThetaDeg();
            thetaDegB = thetaDegA;
            azimuthDegA = 0.0f;
            azimuthDegB = 0.0f;
            eInfA = new Vector4(0, 0, 0, 1);
            eInfB = eInfA;
            blend = roamBlend;
            blendActive = boundIndexB >= 0;
            if (boundIndexA < 0)
            {
                return false;
            }
            if (boundSetIsDescent)
            {
                var entryA = descentManifest.keyframes[boundIndexA];
                azimuthDegA = DescentEntryAzimuthBlDeg(entryA);
                eInfA = EInfVector(entryA);
                if (blendActive)
                {
                    var entryB = descentManifest.keyframes[boundIndexB];
                    azimuthDegB = DescentEntryAzimuthBlDeg(entryB);
                    eInfB = EInfVector(entryB);
                }
            }
            else
            {
                float wA = manifest.skyBlueshiftPerKeyframe != null && boundIndexA < manifest.skyBlueshiftPerKeyframe.Length
                    ? 1.0f / Mathf.Max(manifest.skyBlueshiftPerKeyframe[boundIndexA], 1.0e-3f)
                    : 1.0f;
                eInfA = new Vector4(0, 0, 0, wA);
                if (blendActive)
                {
                    float wB = manifest.skyBlueshiftPerKeyframe != null && boundIndexB < manifest.skyBlueshiftPerKeyframe.Length
                        ? 1.0f / Mathf.Max(manifest.skyBlueshiftPerKeyframe[boundIndexB], 1.0e-3f)
                        : 1.0f;
                    eInfB = new Vector4(0, 0, 0, wB);
                }
            }
            return true;
        }

        /// <summary>
        /// BL label of a descent keyframe: `phi_bl = phi_ks - shift(r_i)`,
        /// evaluated at that keyframe's OWN radius (the shift is strongly
        /// r-dependent near the horizon, so a single shift for the whole
        /// sequence would be wrong by up to hundreds of degrees).
        /// </summary>
        private float DescentEntryAzimuthBlDeg(DescentKeyframeEntry entry)
        {
            return descentHandoffAzimuthKsDeg + entry.azimuthDeg
                - KerrObserverBasis.BlToKsPhiShiftDeg(MetricMassM, MetricSpinA, entry.r_obs);
        }

        public string StatusText()
        {
            if (!IsReady)
            {
                return loadError ?? "Roam: manifest not loaded.";
            }
            float radius = targetRadius > 0.0f ? targetRadius : DefaultRadiusM;
            string modeText = mode == RoamMode.Descent
                ? $"DESCENT (schema {SupportedDescentSchema}, {(DescentAvailable ? descentManifest.thetaDegrees[descentThetaIndex] : 0):F0} deg row)"
                : "grid";
            string binding = boundIndexA >= 0
                ? $"pair {boundIndexA}/{boundIndexB} blend {roamBlend:F2}"
                : "binding...";
            return
                $"Roam {modeText} r_obs={radius:F2}M theta={BoundThetaDeg:F1} (bound row) ({binding})\n" +
                "Crossfade of two traced images; intermediate radii are not solved. No boost between keyframes.";
        }

        // ---------------------------------------------------------------------
        // Binding machinery
        // ---------------------------------------------------------------------

        private void UpdateBinding()
        {
            float radius = targetRadius > 0.0f ? targetRadius : DefaultRadiusM;
            float[] radii = ActiveRadii();
            Keyframe[] cache = ActiveCache();
            int outer = OuterIndex(radius);
            int inner = Mathf.Min(outer + 1, radii.Length - 1);
            int flatOuter = FlatIndex(outer);
            int flatInner = FlatIndex(inner);

            RequestKeyframe(cache, flatOuter, ActiveDirRoot(), ActiveDirs()[flatOuter]);
            RequestKeyframe(cache, flatInner, ActiveDirRoot(), ActiveDirs()[flatInner]);
            if (outer > 0)
            {
                RequestKeyframe(cache, FlatIndex(outer - 1), ActiveDirRoot(), ActiveDirs()[FlatIndex(outer - 1)]);
            }
            if (inner < radii.Length - 1)
            {
                RequestKeyframe(cache, FlatIndex(inner + 1), ActiveDirRoot(), ActiveDirs()[FlatIndex(inner + 1)]);
            }
            PromoteFinishedLoads(cache);
            ReleaseFar(cache, flatOuter, flatInner);

            bool outerReady = cache[flatOuter].State == KeyframeState.Ready;
            bool innerReady = cache[flatInner].State == KeyframeState.Ready;
            if (!outerReady && !innerReady)
            {
                return;
            }
            ResolveMaterial();
            if (targetMaterial == null)
            {
                return;
            }

            if (outerReady && innerReady && flatOuter != flatInner)
            {
                BindPair(cache, flatOuter, flatInner);
                roamBlend = LogWeight(radii[outer], radii[inner], radius);
                targetMaterial.SetFloat("_RoamBlend", roamBlend);
                targetMaterial.SetFloat("_LensRObs", Mathf.Lerp(radii[outer], radii[inner], roamBlend));
            }
            else
            {
                int flat = outerReady ? flatOuter : flatInner;
                BindSingle(cache, flat);
                roamBlend = 0.0f;
                targetMaterial.SetFloat("_LensRObs", radii[outerReady ? outer : inner]);
            }
        }

        private void BindPair(Keyframe[] cache, int flatA, int flatB)
        {
            BindSlots(cache[flatA], SetASlots);
            BindSlots(cache[flatB], SetBSlots);
            boundIndexA = flatA;
            boundIndexB = flatB;
            boundSetIsDescent = mode == RoamMode.Descent;
            ApplySharedState();
            targetMaterial.EnableKeyword("GRBHXR_ROAM_BLEND");
        }

        private void BindSingle(Keyframe[] cache, int flat)
        {
            BindSlots(cache[flat], SetASlots);
            boundIndexA = flat;
            boundIndexB = -1;
            boundSetIsDescent = mode == RoamMode.Descent;
            roamBlend = 0.0f;
            targetMaterial.SetFloat("_RoamBlend", 0.0f);
            ApplySharedState();
            targetMaterial.DisableKeyword("GRBHXR_ROAM_BLEND");
        }

        private void BindSlots(Keyframe keyframe, string[] slots)
        {
            targetMaterial.SetTexture(slots[0], keyframe.EventCube);
            targetMaterial.SetTexture(slots[1], keyframe.EscapeDirCube);
            targetMaterial.SetTexture(slots[2], keyframe.DiskOrder0Cube);
            targetMaterial.SetTexture(slots[3], keyframe.DiskOrder1Cube);
            targetMaterial.SetTexture(slots[4], keyframe.DiskOrder0RedshiftCube);
            targetMaterial.SetTexture(slots[5], keyframe.DiskOrder1RedshiftCube);
        }

        private void ApplySharedState()
        {
            targetMaterial.SetFloat("_UseFullSkyTransfer", 1.0f);
            targetMaterial.SetFloat("_UseDiskTransfer", 1.0f);
            targetMaterial.SetFloat("_UseDiskCoverageTransfer", 1.0f);
            // Collapse the single-radius hybrid window (off would select the
            // legacy full-screen 2D mode).
            targetMaterial.SetFloat("_UseAngularWindow", 1.0f);
            targetMaterial.SetVector("_LensScreenBounds", new Vector4(1.0f, -1.0f, 1.0f, -1.0f));
            // Observer factors ride through _ObsEInf; keep the legacy scalar
            // neutral so the two mechanisms never double-count.
            targetMaterial.SetFloat("_SkyBlueshift", 1.0f);
        }

        // ---------------------------------------------------------------------
        // Cache helpers
        // ---------------------------------------------------------------------

        private void RequestKeyframe(Keyframe[] cache, int flat, string root, string dirName)
        {
            Keyframe keyframe = cache[flat];
            if (keyframe.State != KeyframeState.Unloaded)
            {
                return;
            }
            string keyframeDir = Path.Combine(root, dirName);
            keyframe.State = KeyframeState.LoadingBytes;
            keyframe.BytesTask = Task.Run(() =>
            {
                var buffers = new byte[KeyframeFileNames.Length][];
                for (int i = 0; i < KeyframeFileNames.Length; i += 1)
                {
                    buffers[i] = File.ReadAllBytes(Path.Combine(keyframeDir, KeyframeFileNames[i]));
                }
                return buffers;
            });
        }

        private void PromoteFinishedLoads(Keyframe[] cache)
        {
            for (int i = 0; i < cache.Length; i += 1)
            {
                Keyframe keyframe = cache[i];
                if (keyframe.State != KeyframeState.LoadingBytes || !keyframe.BytesTask.IsCompleted)
                {
                    continue;
                }
                if (keyframe.BytesTask.IsFaulted)
                {
                    Debug.LogError(
                        $"GR-BH-XR roam keyframe {i} load failed: " +
                        $"{keyframe.BytesTask.Exception?.GetBaseException().Message}"
                    );
                    keyframe.BytesTask = null;
                    keyframe.State = KeyframeState.Unloaded;
                    continue;
                }
                byte[][] buffers = keyframe.BytesTask.Result;
                keyframe.BytesTask = null;
                BuildKeyframeTextures(keyframe, i, buffers, ActiveFaceSize());
                break;
            }
        }

        private void ReleaseFar(Keyframe[] cache, int flatOuter, int flatInner)
        {
            float[] radii = ActiveRadii();
            int radiusCount = radii.Length;
            for (int i = 0; i < cache.Length; i += 1)
            {
                if (i == flatOuter || i == flatInner || i == boundIndexA || i == boundIndexB)
                {
                    continue;
                }
                int radiusIndex = i % radiusCount;
                int outerRadius = flatOuter % radiusCount;
                if (Mathf.Abs(radiusIndex - outerRadius) > 2 || (i / radiusCount) != (flatOuter / radiusCount))
                {
                    ReleaseKeyframe(cache[i]);
                }
            }
        }

        private static void ReleaseAll(Keyframe[] cache)
        {
            if (cache == null)
            {
                return;
            }
            foreach (Keyframe keyframe in cache)
            {
                ReleaseKeyframe(keyframe, force: true);
            }
        }

        private static void ReleaseKeyframe(Keyframe keyframe, bool force = false)
        {
            if (keyframe.State == KeyframeState.LoadingBytes && !force)
            {
                return;
            }
            DestroyTexture(ref keyframe.EventCube);
            DestroyTexture(ref keyframe.EscapeDirCube);
            DestroyTexture(ref keyframe.DiskOrder0Cube);
            DestroyTexture(ref keyframe.DiskOrder1Cube);
            DestroyTexture(ref keyframe.DiskOrder0RedshiftCube);
            DestroyTexture(ref keyframe.DiskOrder1RedshiftCube);
            if (keyframe.State != KeyframeState.LoadingBytes)
            {
                keyframe.State = KeyframeState.Unloaded;
            }
        }

        private static void BuildKeyframeTextures(Keyframe keyframe, int index, byte[][] buffers, int faceSize)
        {
            keyframe.EventCube = BlackHoleLensMap.LoadRawCubemapBytes(
                buffers[0], faceSize, TextureFormat.RGBA32, 4,
                $"GR-BH-XR roam kf{index:000} event_cube", FilterMode.Point);
            keyframe.EscapeDirCube = BlackHoleLensMap.LoadRawCubemapBytes(
                buffers[1], faceSize, TextureFormat.RGBAFloat, 16,
                $"GR-BH-XR roam kf{index:000} escape_dir_cube", FilterMode.Bilinear);
            keyframe.DiskOrder0Cube = BlackHoleLensMap.LoadRawCubemapBytes(
                buffers[2], faceSize, TextureFormat.RGBAHalf, 8,
                $"GR-BH-XR roam kf{index:000} disk_order0_cube", FilterMode.Bilinear);
            keyframe.DiskOrder1Cube = BlackHoleLensMap.LoadRawCubemapBytes(
                buffers[3], faceSize, TextureFormat.RGBAHalf, 8,
                $"GR-BH-XR roam kf{index:000} disk_order1_cube", FilterMode.Bilinear);
            keyframe.DiskOrder0RedshiftCube = BlackHoleLensMap.LoadRawCubemapBytes(
                buffers[4], faceSize, TextureFormat.RGBAHalf, 8,
                $"GR-BH-XR roam kf{index:000} disk_order0_redshift_cube", FilterMode.Bilinear);
            keyframe.DiskOrder1RedshiftCube = BlackHoleLensMap.LoadRawCubemapBytes(
                buffers[5], faceSize, TextureFormat.RGBAHalf, 8,
                $"GR-BH-XR roam kf{index:000} disk_order1_redshift_cube", FilterMode.Bilinear);
            keyframe.State = KeyframeState.Ready;
        }

        /// <summary>Synchronous load-and-bind for editor gate captures and tests.</summary>
        public void ForceBind(float radius, float thetaDeg)
        {
            LoadManifest();
            if (!IsReady)
            {
                throw new InvalidOperationException(loadError ?? "Roam keyframes not ready.");
            }
            targetThetaDeg = ClampThetaDeg(thetaDeg);
            float[] radii = ActiveRadii();
            targetRadius = Mathf.Clamp(radius, radii[radii.Length - 1], radii[0]);
            int outer = OuterIndex(targetRadius);
            int flat = FlatIndex(outer);
            Keyframe[] cache = ActiveCache();
            if (cache[flat].State != KeyframeState.Ready)
            {
                string dir = Path.Combine(ActiveDirRoot(), ActiveDirs()[flat]);
                var buffers = new byte[KeyframeFileNames.Length][];
                for (int i = 0; i < KeyframeFileNames.Length; i += 1)
                {
                    buffers[i] = File.ReadAllBytes(Path.Combine(dir, KeyframeFileNames[i]));
                }
                BuildKeyframeTextures(cache[flat], flat, buffers, ActiveFaceSize());
            }
            ResolveMaterial();
            BindSingle(cache, flat);
        }

        /// <summary>Synchronous descent bind for gate captures (incl. interior radii).</summary>
        public void ForceBindDescent(float radius, float thetaDeg)
        {
            LoadManifest();
            if (!DescentAvailable)
            {
                throw new InvalidOperationException("Descent manifest not available.");
            }
            EnterDescent(thetaDeg, 0.0f);
            ForceBind(radius, thetaDeg);
        }

        // ---------------------------------------------------------------------
        // Manifest parsing and lookups
        // ---------------------------------------------------------------------

        private RoamKeyframesManifest ParseGridManifest(out Keyframe[] cache, out float[] logs)
        {
            cache = null;
            logs = null;
            string manifestPath = Path.Combine(Application.streamingAssetsPath, manifestRelativePath);
            try
            {
                if (!File.Exists(manifestPath))
                {
                    loadError = $"Roam manifest not found: {manifestPath}";
                    // Loudly: with no manifest the entire roam system is inert
                    // and every locomotion control silently does nothing. This
                    // also fires on Android/Quest-native builds, where
                    // StreamingAssets lives inside the APK and cannot be read
                    // through System.IO at all - roam playback is PCVR-only.
                    Debug.LogWarning($"GR-BH-XR roam disabled: {loadError}");
                    return null;
                }
                var parsed = JsonUtility.FromJson<RoamKeyframesManifest>(File.ReadAllText(manifestPath));
                if (
                    parsed == null || parsed.schema != SupportedSchema || parsed.faceSize < 2 ||
                    parsed.radiiM == null || parsed.thetaDegrees == null || parsed.keyframeDirs == null ||
                    parsed.keyframeDirs.Length != parsed.radiiM.Length * parsed.thetaDegrees.Length
                )
                {
                    loadError = $"Roam manifest malformed or wrong schema: {manifestPath}";
                    return null;
                }
                cache = NewCache(parsed.keyframeDirs.Length);
                logs = new float[parsed.radiiM.Length];
                for (int i = 0; i < logs.Length; i += 1)
                {
                    logs[i] = Mathf.Log(parsed.radiiM[i]);
                }
                Debug.Log(
                    $"GR-BH-XR roam grid loaded: {parsed.thetaDegrees.Length} theta rows x " +
                    $"{parsed.radiiM.Length} radii, faceSize={parsed.faceSize}."
                );
                return parsed;
            }
            catch (Exception exception)
            {
                loadError = $"Roam manifest load failed: {exception.Message}";
                return null;
            }
        }

        private DescentManifest ParseDescentManifest(out Keyframe[] cache, out float[] logs)
        {
            cache = null;
            logs = null;
            string manifestPath = Path.Combine(Application.streamingAssetsPath, descentManifestRelativePath);
            try
            {
                if (!File.Exists(manifestPath))
                {
                    // Descent is optional, but its absence must be visible:
                    // it is what makes the free-fall control unavailable, and
                    // its producer is not on this branch.
                    Debug.Log(
                        "GR-BH-XR descent keyframes not bound (optional): " +
                        $"{manifestPath}. Free fall stays disabled."
                    );
                    return null;
                }
                var parsed = JsonUtility.FromJson<DescentManifest>(File.ReadAllText(manifestPath));
                if (
                    parsed == null || parsed.schema != SupportedDescentSchema || parsed.faceSize < 2 ||
                    parsed.radiiM == null || parsed.thetaDegrees == null || parsed.keyframes == null ||
                    parsed.keyframes.Length != parsed.radiiM.Length * parsed.thetaDegrees.Length
                )
                {
                    Debug.LogWarning($"GR-BH-XR descent manifest malformed: {manifestPath}");
                    return null;
                }
                cache = NewCache(parsed.keyframes.Length);
                logs = new float[parsed.radiiM.Length];
                for (int i = 0; i < logs.Length; i += 1)
                {
                    logs[i] = Mathf.Log(parsed.radiiM[i]);
                }
                Debug.Log(
                    $"GR-BH-XR descent loaded: {parsed.thetaDegrees.Length} rows x {parsed.radiiM.Length} radii " +
                    $"down to r={parsed.radiiM[parsed.radiiM.Length - 1]:F2}M (through the horizon)."
                );
                return parsed;
            }
            catch (Exception exception)
            {
                Debug.LogWarning($"GR-BH-XR descent manifest load failed: {exception.Message}");
                return null;
            }
        }

        private static Keyframe[] NewCache(int count)
        {
            var cache = new Keyframe[count];
            for (int i = 0; i < count; i += 1)
            {
                cache[i] = new Keyframe();
            }
            return cache;
        }

        private static Vector4 EInfVector(DescentKeyframeEntry entry)
        {
            if (entry.eInf == null || entry.eInf.Length != 4)
            {
                return new Vector4(0, 0, 0, 1);
            }
            return new Vector4(entry.eInf[0], entry.eInf[1], entry.eInf[2], entry.eInf[3]);
        }

        private float CurrentThetaDeg()
        {
            if (mode == RoamMode.Descent && DescentAvailable)
            {
                return descentManifest.thetaDegrees[descentThetaIndex];
            }
            if (!IsReady)
            {
                return startThetaDeg;
            }
            float theta = targetThetaDeg > 0.0f ? targetThetaDeg : StartThetaDeg;
            return manifest.thetaDegrees[NearestIndex(manifest.thetaDegrees, theta)];
        }

        private float[] ActiveRadii() => mode == RoamMode.Descent ? descentManifest.radiiM : manifest.radiiM;
        private Keyframe[] ActiveCache() => mode == RoamMode.Descent ? descentKeyframes : keyframes;
        private int ActiveFaceSize() => mode == RoamMode.Descent ? descentManifest.faceSize : manifest.faceSize;

        private string ActiveDirRoot()
        {
            string relative = mode == RoamMode.Descent ? descentManifestRelativePath : manifestRelativePath;
            return Path.GetDirectoryName(Path.Combine(Application.streamingAssetsPath, relative))
                ?? Application.streamingAssetsPath;
        }

        private string[] ActiveDirs() => mode == RoamMode.Descent
            ? descentManifest.keyframeDirs
            : manifest.keyframeDirs;

        private int FlatIndex(int radiusIndex)
        {
            int radiusCount = ActiveRadii().Length;
            int thetaIndex = mode == RoamMode.Descent
                ? descentThetaIndex
                : NearestIndex(manifest.thetaDegrees, CurrentThetaDeg());
            return thetaIndex * radiusCount + radiusIndex;
        }

        private int OuterIndex(float radius) => OuterIndexIn(ActiveRadii(), radius);

        private static int OuterIndexIn(float[] radii, float radius)
        {
            // Radii descend; the outer bracket is the last index with r >= radius.
            int outer = 0;
            for (int i = 0; i < radii.Length; i += 1)
            {
                if (radii[i] >= radius)
                {
                    outer = i;
                }
                else
                {
                    break;
                }
            }
            return Mathf.Min(outer, radii.Length - 2 >= 0 ? radii.Length - 1 : 0);
        }

        private static float LogWeight(float outerRadius, float innerRadius, float radius)
        {
            float span = Mathf.Log(outerRadius) - Mathf.Log(innerRadius);
            if (Mathf.Abs(span) < 1.0e-6f)
            {
                return 0.0f;
            }
            return Mathf.Clamp01((Mathf.Log(outerRadius) - Mathf.Log(radius)) / span);
        }

        private static int NearestIndex(float[] values, float target)
        {
            int best = 0;
            float bestDistance = float.MaxValue;
            for (int i = 0; i < values.Length; i += 1)
            {
                float distance = Mathf.Abs(values[i] - target);
                if (distance < bestDistance)
                {
                    bestDistance = distance;
                    best = i;
                }
            }
            return best;
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
                var renderer = shell.GetComponent<Renderer>();
                if (renderer != null)
                {
                    targetMaterial = renderer.sharedMaterial;
                }
            }
        }

        private static void DestroyTexture(ref Cubemap texture)
        {
            if (texture == null)
            {
                return;
            }
            if (Application.isPlaying)
            {
                Destroy(texture);
            }
            else
            {
                DestroyImmediate(texture);
            }
            texture = null;
        }
    }
}
