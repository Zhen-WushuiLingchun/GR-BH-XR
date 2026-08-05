using System;
using UnityEngine;

namespace GRBHXR
{
    /// <summary>
    /// Real-time Kerr transfer-map solver: dispatches the Kerr-Schild compute
    /// tracer over the full sky in per-frame batches, always from the CURRENT
    /// virtual observer position. Each pass runs a full-texel trace phase and
    /// a limb-refine phase (3x3 subrays at event-mask discontinuities for
    /// fractional-coverage anti-aliasing), then HARD-swaps the completed
    /// snapshot into display - the view is always exactly one complete
    /// solution at one position, never a mixture. Keyframe playback remains
    /// as the instant-on fallback while the first snapshot converges.
    /// </summary>
    public sealed class BlackHoleLiveTracer : MonoBehaviour
    {
        private sealed class Snapshot
        {
            // Compute writes into Tex2DArray staging (cube UAV binding is not
            // reliable on D3D11); completed passes are GPU-copied face by face
            // into the sampled cube textures.
            public RenderTexture StagingEscapeDir;
            public RenderTexture StagingEvent;
            public RenderTexture StagingDisk0;
            public RenderTexture StagingDisk1;
            public RenderTexture StagingRedshift0;
            public RenderTexture StagingRedshift1;
            public RenderTexture EscapeDir;
            public RenderTexture Event;
            public RenderTexture Disk0;
            public RenderTexture Disk1;
            public RenderTexture Redshift0;
            public RenderTexture Redshift1;
            public Vector4 EInf;
            public float RadiusM;
            public bool Valid;
            // Faces are sized per snapshot so a resolution change reallocates
            // only the back buffer while the front keeps displaying.
            public int Size;
            // Pass origin (virtual observer state + metric parameters the
            // pass was solved at - mass/spin edits invalidate like motion).
            public float OriginR;
            public float OriginTheta;
            public float OriginAz;
            public float OriginMass;
            public float OriginSpin;
        }

        private sealed class WindowSnapshot
        {
            // 2D UAV targets are reliable on D3D11 (the cube-UAV trap does
            // not apply), so the window writes straight into sampled RTs.
            public RenderTexture Dir;
            public RenderTexture Event;
            public RenderTexture Disk0;
            public RenderTexture Disk1;
            public RenderTexture Redshift0;
            public RenderTexture Redshift1;
            public int Size;
            public float HalfAlpha;
            public float OriginR;
            public float OriginTheta;
            public float OriginAz;
            public float OriginMass;
            public float OriginSpin;
            public bool Valid;
        }

        [SerializeField] private ComputeShader tracerCompute;
        [SerializeField] private Material targetMaterial;
        [SerializeField] private BlackHoleObserverRigControls observerRig;
        [SerializeField] private BlackHoleRoamKeyframes roamKeyframes;
        [SerializeField] private int faceSize = 128;
        [SerializeField] private int targetPassFrames = 2;
        // Distance-adaptive angular resolution: the shadow shrinks like
        // asin(sqrt(27) M / r), so a fixed cube resolution pixelates at large
        // radius. Auto mode keeps the shadow diameter sampled by a roughly
        // constant texel count; the per-frame ray budget stays fixed, so
        // higher resolutions refresh over more frames (exactly where the map
        // changes most slowly with position).
        [SerializeField] private bool autoResolution = true;
        [SerializeField] private bool liveTracingEnabled = true;
        // High-resolution angular window around the hole: traced only while
        // the observer is stationary (the cube handles motion), converges to
        // near-headset angular density over the strong-field region, and is
        // displayed ONLY when its pass origin matches the displayed cube's -
        // stale sharp data is never mixed with fresh data.
        [SerializeField] private bool liveWindowEnabled = true;
        [SerializeField] private float windowDensityPxPerDeg = 20.0f;
        [SerializeField] private float mass = 1.0f;
        [SerializeField] private float spin = 0.9f;
        // Integration controls. UNITS AUDIT - each of these is a geometric
        // length or an affine length and is currently an ABSOLUTE value, i.e.
        // it does NOT scale with the mass slider (0.5-2.0 M). That is a
        // deliberate, documented choice for the integrator budget rather than
        // a physical statement, and it is recorded here because the horizon
        // guard next to it WAS silently absolute and had to be fixed:
        //   stepSize / maxStep / stepRRef : geometric lengths. Holding them
        //     fixed makes the effective step finer at M = 2 and coarser at
        //     M = 0.5 in units of M - conservative at large M, and the
        //     Hamiltonian residual gate is what actually bounds accuracy.
        //   maxLambda : affine length, same reasoning.
        //   rEscape : geometric length. At M = 2 this is 100 M rather than
        //     200 M, so the asymptotic-direction approximation is evaluated
        //     closer in; the dump publishes rEscape so the Python gate uses
        //     the same value and the comparison stays exact.
        //   maxSteps : dimensionless.
        // Anything that must agree with the Python reference is published in
        // the validation dump rather than restated on both sides. Do not
        // "fix" these by multiplying by mass without re-running the gate.
        [SerializeField] private float stepSize = 0.01f;
        [SerializeField] private float maxStep = 1.0f;
        [SerializeField] private float stepRRef = 5.0f;
        [SerializeField] private int maxSteps = 60000;
        [SerializeField] private float maxLambda = 1500.0f;
        [SerializeField] private float rEscape = 200.0f;

        // Double buffer with HARD swap: the display always shows exactly one
        // complete solution at one position - never a mixture (a dissolve of
        // two exact images at different radii superimposes two photon rings).
        private readonly Snapshot[] snapshots = { new Snapshot(), new Snapshot() };
        private int backIndex = 1;
        private int frontIndex = 0;
        private int nextTexel;
        private bool refinePhase;
        private bool passActive;
        private int passFaceSize = 128;
        private int autoFaceSize = 128;
        private float passStartTime;
        private float lastPassDuration = 0.05f;
        private int kernel = -1;
        private int refineKernel = -1;
        private int windowKernel = -1;
        private int windowRefineKernel = -1;
        private ComputeBuffer eventMaskBuffer;
        private ComputeBuffer classBuffer;
        private ComputeBuffer hMaxBuffer;

        /// <summary>
        /// Hamiltonian-residual validity threshold. H is identically zero for
        /// a null geodesic, so max|H| along the ray is a first-principles
        /// criterion - observer-radius independent and spin independent -
        /// unlike the launch-radius and affine-length heuristics it replaces.
        ///
        /// 1e-2 is the accepted value from
        /// gr_bh_xr.gpu.generate_descent_keyframes.DEFAULT_HAMILTONIAN_MAX and
        /// transfers verbatim because it was calibrated on the SAME f32
        /// tracer. It is not tuned: at the accepted near-horizon keyframe the
        /// kept population tops out at ~1.8e-5 and the rejected population
        /// starts at ~1.7e4, so every threshold in [1e-4, 1e0] selects the
        /// identical set and f32 rounding cannot move a ray across.
        ///
        /// Published in the validation dump so the Python gate consumes it
        /// rather than restating it.
        /// </summary>
        [SerializeField] private float hamiltonianMax = 1.0e-2f;
        public float HamiltonianMax => hamiltonianMax;
        private ComputeBuffer windowMaskBuffer;
        private Texture2D diskRadialLutTexture;
        private bool diskLutDirty = true;
        private bool warmed;
        private readonly int[] faceOrder = { 0, 1, 2, 3, 4, 5 };

        // Window pass state (runs only while the cube is converged and the
        // observer is stationary; abandoned on motion).
        private readonly WindowSnapshot[] windowSnapshots = { new WindowSnapshot(), new WindowSnapshot() };
        private int windowFrontIndex = 0;
        private int windowBackIndex = 1;
        private bool windowPassActive;
        private bool windowRefinePhase;
        private int windowNextTexel;

        private static readonly int[] ResolutionLadder = { 96, 128, 192, 256, 384, 512 };
        private static readonly int[] WindowLadder = { 512, 768, 1024, 1536, 2048 };

        // Row count of the runtime-built Page-Thorne radial LUT. Published to
        // the shader in _DiskRadialLutBounds.z so the endpoint-row texel
        // coordinate matches the Python LUT producer's published contract.
        private const int RadialLutSamples = 512;

        /// <summary>
        /// Relative cylindrical radius below which the rain frame is refused.
        /// Mirrors gr_bh_xr.observers.RAIN_MIN_SIN_THETA.
        /// </summary>
        private const double RainMinSinTheta = 1.0e-6;

        /// <summary>
        /// Numerical guard band outside the outer horizon, as a FRACTION OF M.
        /// This is a geometric length: written as a bare 0.05 it silently means
        /// 0.05 in world units, so every horizon-relative threshold broke scale
        /// invariance the moment the mass slider left M = 1 (the slider spans
        /// 0.5-2.0 M, i.e. a factor of 4 in the guard's physical size).
        /// </summary>
        private const double HorizonGuardOverM = 0.05;

        /// <summary>Outer horizon plus the M-scaled numerical guard band.</summary>
        private float HorizonGuardRadius()
        {
            float rPlus = mass + Mathf.Sqrt(Mathf.Max(mass * mass - spin * spin, 0.0f));
            return rPlus + (float)HorizonGuardOverM * mass;
        }

        /// <summary>
        /// Termination radius, matching `gr_bh_xr.geodesic_ks._inner_capture_radius`
        /// exactly: `max(1e-4, r_- + min(0.05 M, 0.25 (r_+ - r_-)))` for the
        /// past-directed (rain) branch. Two corrections over the previous bare
        /// inner-horizon offset: the guard now scales with M, and the
        /// `0.25 * gap` clamp is applied, without which the two
        /// implementations diverge for |a|/M above 0.994987 - inside the 0.998
        /// the spin slider allows.
        ///
        /// The static and rain branches remain deliberately DIFFERENT surfaces:
        /// the exterior branch terminates just OUTSIDE r_+ (a numerical guard,
        /// physically harmless because r_+ + 0.05 M is inside the innermost
        /// photon orbit) while the past-directed branch must reach inside it.
        /// Only the missing M factor is fixed here.
        /// </summary>
        private float CaptureRadius(bool pastTracing)
        {
            float rPlus = mass + Mathf.Sqrt(Mathf.Max(mass * mass - spin * spin, 0.0f));
            float rMinus = mass - Mathf.Sqrt(Mathf.Max(mass * mass - spin * spin, 0.0f));
            if (!pastTracing)
            {
                return HorizonGuardRadius();
            }
            float margin = Mathf.Min((float)HorizonGuardOverM * mass, 0.25f * (rPlus - rMinus));
            return Mathf.Max(1.0e-4f, rMinus + margin);
        }

        public bool LiveTracingEnabled => liveTracingEnabled;
        public float LastPassDuration => lastPassDuration;
        public int FaceSize => passFaceSize;

        /// <summary>
        /// Cycle the live angular resolution: auto (distance-adaptive), then
        /// the manual ladder 96..512, then back to auto. The switch only
        /// changes what the NEXT pass allocates - the front snapshot keeps
        /// displaying, so cycling never blanks the view.
        /// </summary>
        public void CycleResolution()
        {
            if (autoResolution)
            {
                autoResolution = false;
                faceSize = ResolutionLadder[0];
            }
            else
            {
                int index = Array.IndexOf(ResolutionLadder, faceSize);
                if (index < 0 || index >= ResolutionLadder.Length - 1)
                {
                    autoResolution = true;
                }
                else
                {
                    faceSize = ResolutionLadder[index + 1];
                }
            }
            Debug.Log(
                autoResolution
                    ? "GR-BH-XR live resolution -> auto (distance-adaptive)."
                    : $"GR-BH-XR live resolution -> {faceSize} per face (manual)."
            );
        }

        /// <summary>
        /// Distance-adaptive face size: keep the shadow diameter sampled by
        /// at least ~40 texels. The shadow angular radius uses the far-field
        /// idiom asin(sqrt(27) M / r) - a sampling heuristic only, physics is
        /// unaffected. Hysteresis: stepping DOWN also has to hold at a 15%
        /// larger radius, so the ladder cannot ping-pong at a band edge.
        /// </summary>
        private int DesiredFaceSize(float radiusM)
        {
            if (!autoResolution)
            {
                return faceSize;
            }
            int target = AutoLadderSize(radiusM);
            if (target > autoFaceSize)
            {
                autoFaceSize = target;
            }
            else if (AutoLadderSize(radiusM * 1.15f) < autoFaceSize)
            {
                autoFaceSize = target;
            }
            return autoFaceSize;
        }

        private int AutoLadderSize(float radiusM)
        {
            float sinShadow = Mathf.Clamp01(
                Mathf.Sqrt(27.0f) * mass / Mathf.Max(radiusM, 3.0f * mass));
            float shadowRadians = Mathf.Asin(sinShadow);
            float required = 40.0f / Mathf.Max(shadowRadians, 1.0e-3f);
            for (int i = 1; i < ResolutionLadder.Length; i += 1)
            {
                if (ResolutionLadder[i] >= required)
                {
                    return ResolutionLadder[i];
                }
            }
            return ResolutionLadder[ResolutionLadder.Length - 1];
        }

        public void SetLiveTracing(bool enabledValue)
        {
            liveTracingEnabled = enabledValue;
            if (roamKeyframes != null)
            {
                roamKeyframes.enabled = !enabledValue;
            }
            if (!enabledValue)
            {
                warmed = false;
                passActive = false;
                refinePhase = false;
                nextTexel = 0;
                windowPassActive = false;
                windowRefinePhase = false;
                windowNextTexel = 0;
                if (targetMaterial != null)
                {
                    targetMaterial.DisableKeyword("GRBHXR_ROAM_BLEND");
                    targetMaterial.SetFloat("_UseLiveWindow", 0.0f);
                }
            }
            Debug.Log($"GR-BH-XR live tracing {(enabledValue ? "ON" : "OFF")} (faceSize={passFaceSize}).");
        }

        public void ToggleLiveTracing()
        {
            SetLiveTracing(!liveTracingEnabled);
        }

        public string StatusText()
        {
            if (!liveTracingEnabled)
            {
                return "Live tracing OFF (keyframe playback).";
            }
            string mode = autoResolution ? $"auto {passFaceSize}" : $"manual {faceSize}";
            string window = "off";
            if (liveWindowEnabled)
            {
                WindowSnapshot frontWindow = windowSnapshots[windowFrontIndex];
                if (windowPassActive)
                {
                    WindowSnapshot back = windowSnapshots[windowBackIndex];
                    int total = Mathf.Max(back.Size * back.Size, 1);
                    window = $"{back.Size} solving {100 * windowNextTexel / total}%";
                }
                else if (frontWindow.Valid)
                {
                    window = $"{frontWindow.Size} ready";
                }
                else
                {
                    window = "waiting (stand still to converge)";
                }
            }
            return warmed
                ? $"LIVE tracing: {mode} cube, window {window}, pass {lastPassDuration * 1000.0f:F0} ms."
                : "LIVE tracing warming up...";
        }

        private void Awake()
        {
            ResolveReferences();
        }

        private void Update()
        {
            if (!Application.isPlaying || !liveTracingEnabled || tracerCompute == null)
            {
                return;
            }
            ResolveReferences();
            if (targetMaterial == null || observerRig == null)
            {
                return;
            }
            if (kernel < 0)
            {
                kernel = tracerCompute.FindKernel("TraceTexels");
                refineKernel = tracerCompute.FindKernel("RefineTexels");
                windowKernel = tracerCompute.FindKernel("TraceWindow");
                windowRefineKernel = tracerCompute.FindKernel("RefineWindow");
            }

            // The per-frame ray budget is fixed at the 128-face baseline, so
            // higher resolutions spread one pass over more frames instead of
            // spiking the frame cost.
            int budget = Mathf.Max(6 * 128 * 128 / Mathf.Max(targetPassFrames, 1), 4096);
            Snapshot front = snapshots[frontIndex];
            bool cubeCurrent = front.Valid
                && SameObserverState(front.OriginR, front.OriginTheta, front.OriginAz, front.OriginMass, front.OriginSpin);
            if (passActive || !cubeCurrent)
            {
                // Motion (or warm-up): keep the fast full-sky cube fresh.
                if (!passActive)
                {
                    BeginPass();
                }
                StepCubePass(budget);
            }
            else if (liveWindowEnabled)
            {
                // Stationary and the cube is converged at this exact state:
                // re-solving it would be redundant (the metric is stationary),
                // so the whole budget goes into the high-resolution window.
                StepWindowPass(budget * 2);
            }
            if (warmed)
            {
                BindFrontToMaterial();
            }
        }

        /// <summary>True when the rig's virtual observer state AND the metric
        /// parameters equal the recorded pass origin (exact up to float noise
        /// - locomotion and mass/spin edits change them by finite steps).</summary>
        private bool SameObserverState(float r, float thetaDeg, float azDeg, float originMass, float originSpin)
        {
            return Mathf.Abs(observerRig.VirtualRadiusM - r) < 1.0e-5f * Mathf.Max(r, 1.0f)
                && Mathf.Abs(observerRig.VirtualThetaDeg - thetaDeg) < 1.0e-4f
                && Mathf.Abs(observerRig.VirtualAzimuthDeg - azDeg) < 1.0e-4f
                && mass == originMass
                && spin == originSpin;
        }

        /// <summary>Continuous spin control (falsification affordance: the
        /// live tracer re-solves the metric within a pass, so flipping the
        /// sign must flip beaming side, ISCO, shadow asymmetry, and frame
        /// dragging together). Kerr bound |a| < M enforced.</summary>
        public void AdjustSpin(float delta)
        {
            float previous = spin;
            spin = Mathf.Clamp(spin + delta, -0.998f * mass, 0.998f * mass);
            diskLutDirty = true;
            // Metric changes were previously unlogged and unreadable, so a
            // capture could not be attributed to a spin value after the fact.
            if (!Mathf.Approximately(previous, spin))
            {
                Debug.Log($"GR-BH-XR live metric: a = {spin:F4} (M = {mass:F3}).");
            }
        }

        /// <summary>Continuous mass control (rescales the hole; all radii in
        /// the tracer carry M explicitly).</summary>
        public void AdjustMass(float delta)
        {
            float previous = mass;
            mass = Mathf.Clamp(mass + delta, 0.5f, 2.0f);
            spin = Mathf.Clamp(spin, -0.998f * mass, 0.998f * mass);
            diskLutDirty = true;
            if (!Mathf.Approximately(previous, mass))
            {
                Debug.Log($"GR-BH-XR live metric: M = {mass:F3} (a = {spin:F4}).");
            }
        }

        public float MassValue => mass;
        public float SpinValue => spin;

        /// <summary>Regenerates the Page-Thorne radial LUT (F_norm, T_shape)
        /// for the CURRENT mass/spin, so disk emissivity, temperature shape,
        /// and inner edge stay first-principles under live parameter edits.</summary>
        private void EnsureDiskRadialLut()
        {
            if ((!diskLutDirty && diskRadialLutTexture != null) || targetMaterial == null)
            {
                return;
            }
            double rOut = 30.0 * mass;
            Color[] rows = KerrDiskPhysics.BuildRadialLut(mass, spin, rOut, RadialLutSamples, out double rIsco);
            if (diskRadialLutTexture == null)
            {
                diskRadialLutTexture = new Texture2D(RadialLutSamples, 1, TextureFormat.RGBAFloat, false, true)
                {
                    name = "GR-BH-XR live disk_radial_lut",
                    wrapMode = TextureWrapMode.Clamp,
                    filterMode = FilterMode.Bilinear,
                    hideFlags = HideFlags.DontSave,
                };
            }
            diskRadialLutTexture.SetPixels(rows);
            diskRadialLutTexture.Apply(false, false);
            targetMaterial.SetTexture("_DiskRadialLut", diskRadialLutTexture);
            // .z publishes the row count so the shader can use the producer's
            // endpoint-row texel coordinate (s (samples-1) + 0.5)/samples
            // instead of u = s; the half-texel offset is 0.027 M in radius at
            // 512 rows (0.048 in normalized flux on the steep inner rise).
            targetMaterial.SetVector(
                "_DiskRadialLutBounds",
                new Vector4((float)rIsco, (float)rOut, RadialLutSamples, 0.0f)
            );
            diskLutDirty = false;
        }

        private void StepCubePass(int budget)
        {
            int totalTexels = passFaceSize * passFaceSize * 6;
            if (!refinePhase)
            {
                int count = Mathf.Min(budget, totalTexels - nextTexel);
                tracerCompute.SetInt("_TexelBase", nextTexel);
                tracerCompute.SetInt("_TexelCount", count);
                BindOutputs(kernel, snapshots[backIndex]);
                tracerCompute.Dispatch(kernel, Mathf.CeilToInt(count / 64.0f), 1, 1);
                nextTexel += count;
                if (nextTexel >= totalTexels)
                {
                    refinePhase = true;
                    nextTexel = 0;
                }
            }
            else
            {
                // Limb refine scans are mask reads for all but the ~1% edge
                // texels, so the scan rate can run above the trace budget.
                int count = Mathf.Min(budget * 2, totalTexels - nextTexel);
                tracerCompute.SetInt("_TexelBase", nextTexel);
                tracerCompute.SetInt("_TexelCount", count);
                BindOutputs(refineKernel, snapshots[backIndex]);
                tracerCompute.Dispatch(refineKernel, Mathf.CeilToInt(count / 64.0f), 1, 1);
                nextTexel += count;
                if (nextTexel >= totalTexels)
                {
                    CompletePass();
                }
            }
        }

        private void StepWindowPass(int budget)
        {
            WindowSnapshot back = windowSnapshots[windowBackIndex];
            if (windowPassActive
                && !SameObserverState(back.OriginR, back.OriginTheta, back.OriginAz, back.OriginMass, back.OriginSpin))
            {
                // The observer moved while the window was integrating: a
                // partially traced window would mix two positions. Abandon;
                // restart when stationary again.
                windowPassActive = false;
            }
            WindowSnapshot frontWindow = windowSnapshots[windowFrontIndex];
            if (!windowPassActive
                && frontWindow.Valid
                && SameObserverState(frontWindow.OriginR, frontWindow.OriginTheta, frontWindow.OriginAz, frontWindow.OriginMass, frontWindow.OriginSpin))
            {
                return; // window converged at this position - nothing to do
            }
            if (!windowPassActive)
            {
                BeginWindowPass();
            }

            int totalTexels = back.Size * back.Size;
            if (!windowRefinePhase)
            {
                int count = Mathf.Min(budget, totalTexels - windowNextTexel);
                tracerCompute.SetInt("_TexelBase", windowNextTexel);
                tracerCompute.SetInt("_TexelCount", count);
                BindWindowOutputs(windowKernel, back);
                tracerCompute.Dispatch(windowKernel, Mathf.CeilToInt(count / 64.0f), 1, 1);
                windowNextTexel += count;
                if (windowNextTexel >= totalTexels)
                {
                    windowRefinePhase = true;
                    windowNextTexel = 0;
                }
            }
            else
            {
                int count = Mathf.Min(budget * 2, totalTexels - windowNextTexel);
                tracerCompute.SetInt("_TexelBase", windowNextTexel);
                tracerCompute.SetInt("_TexelCount", count);
                BindWindowOutputs(windowRefineKernel, back);
                tracerCompute.Dispatch(windowRefineKernel, Mathf.CeilToInt(count / 64.0f), 1, 1);
                windowNextTexel += count;
                if (windowNextTexel >= totalTexels)
                {
                    back.Valid = true;
                    (windowFrontIndex, windowBackIndex) = (windowBackIndex, windowFrontIndex);
                    windowPassActive = false;
                    windowRefinePhase = false;
                    windowNextTexel = 0;
                }
            }
        }

        private void BeginWindowPass()
        {
            WindowSnapshot back = windowSnapshots[windowBackIndex];
            float radius = observerRig.VirtualRadiusM;
            int size = DesiredWindowSize(radius);
            EnsureWindowTextures(back, size);
            EnsureWindowMaskBuffer(size);
            back.HalfAlpha = radius * Mathf.Tan(WindowHalfAngleRad(radius));
            back.OriginR = radius;
            back.OriginTheta = observerRig.VirtualThetaDeg;
            back.OriginAz = observerRig.VirtualAzimuthDeg;
            back.OriginMass = mass;
            back.OriginSpin = spin;
            back.Valid = false;
            // Same-state observer uniforms (the cube front is current, so this
            // re-uploads identical tetrad/metric values - kept explicit so the
            // window pass never depends on stale compute-shader state).
            if (!TryConfigureObserverUniforms(snapshots[frontIndex])) { return; }
            tracerCompute.SetInt("_WindowSize", back.Size);
            tracerCompute.SetFloat("_WindowHalfAlpha", back.HalfAlpha);
            tracerCompute.SetFloat("_WindowRObs", radius);
            windowNextTexel = 0;
            windowRefinePhase = false;
            windowPassActive = true;
        }

        /// <summary>Window half-angle: cover the shadow plus the photon ring
        /// and inner strong-lensing zone (2.2x the shadow angular radius),
        /// clamped so the gnomonic map stays well-conditioned.</summary>
        private float WindowHalfAngleRad(float radiusM)
        {
            float sinShadow = Mathf.Clamp01(
                Mathf.Sqrt(27.0f) * mass / Mathf.Max(radiusM, 3.0f * mass));
            float shadow = Mathf.Asin(sinShadow);
            return Mathf.Clamp(2.2f * shadow, 4.0f * Mathf.Deg2Rad, 55.0f * Mathf.Deg2Rad);
        }

        /// <summary>Window resolution targeting a headset-scale angular
        /// density (default 20 texels/deg) across the window diameter.</summary>
        private int DesiredWindowSize(float radiusM)
        {
            float halfDeg = WindowHalfAngleRad(radiusM) * Mathf.Rad2Deg;
            float required = 2.0f * halfDeg * Mathf.Max(windowDensityPxPerDeg, 1.0f);
            foreach (int size in WindowLadder)
            {
                if (size >= required)
                {
                    return size;
                }
            }
            return WindowLadder[WindowLadder.Length - 1];
        }

        private void BeginPass()
        {
            passStartTime = Time.realtimeSinceStartup;
            Snapshot back = snapshots[backIndex];
            passFaceSize = DesiredFaceSize(observerRig.VirtualRadiusM);
            EnsureSnapshotTextures(back, passFaceSize);
            EnsureEventMaskBuffer(passFaceSize);
            back.RadiusM = observerRig.VirtualRadiusM;
            back.OriginR = observerRig.VirtualRadiusM;
            back.OriginTheta = observerRig.VirtualThetaDeg;
            back.OriginAz = observerRig.VirtualAzimuthDeg;
            back.OriginMass = mass;
            back.OriginSpin = spin;
            EnsureDiskRadialLut();
            if (!TryConfigureObserverUniforms(back)) { return; }
            UpdateFacePriority();
            nextTexel = 0;
            refinePhase = false;
            passActive = true;
        }

        private void CompletePass()
        {
            Snapshot back = snapshots[backIndex];
            CopyStagingToCubes(back);
            back.Valid = true;
            lastPassDuration = Mathf.Max(Time.realtimeSinceStartup - passStartTime, 1.0f / 90.0f);
            // HARD swap: the newest complete solution becomes the one and only
            // displayed map. No dissolve - a blend of two exact images at
            // different radii would superimpose two photon rings.
            (frontIndex, backIndex) = (backIndex, frontIndex);
            warmed = snapshots[frontIndex].Valid;
            passActive = false;
            refinePhase = false;
            nextTexel = 0;
        }

        private static void CopyStagingToCubes(Snapshot snapshot)
        {
            for (int face = 0; face < 6; face += 1)
            {
                Graphics.CopyTexture(snapshot.StagingEscapeDir, face, snapshot.EscapeDir, face);
                Graphics.CopyTexture(snapshot.StagingEvent, face, snapshot.Event, face);
                Graphics.CopyTexture(snapshot.StagingDisk0, face, snapshot.Disk0, face);
                Graphics.CopyTexture(snapshot.StagingDisk1, face, snapshot.Disk1, face);
                Graphics.CopyTexture(snapshot.StagingRedshift0, face, snapshot.Redshift0, face);
                Graphics.CopyTexture(snapshot.StagingRedshift1, face, snapshot.Redshift1, face);
            }
        }

        /// <summary>
        /// View-priority face ordering: the faces most aligned with the
        /// current gaze are integrated first within each pass, so the visible
        /// region is always the freshest.
        /// </summary>
        private void UpdateFacePriority()
        {
            Vector3 view = Camera.main != null ? Camera.main.transform.forward : Vector3.forward;
            var anchor = FindAnyObjectByType<BlackHoleLensAnchorControls>();
            Quaternion rotation = anchor != null ? anchor.transform.rotation : Quaternion.identity;
            Vector3 local = Quaternion.Inverse(rotation) * view;
            Vector3[] faceDirs =
            {
                Vector3.right, Vector3.left, Vector3.up, Vector3.down, Vector3.forward, Vector3.back,
            };
            var order = new int[6] { 0, 1, 2, 3, 4, 5 };
            Array.Sort(order, (a, b) =>
                Vector3.Dot(faceDirs[b], local).CompareTo(Vector3.Dot(faceDirs[a], local)));
            int packed = 0;
            for (int i = 0; i < 6; i += 1)
            {
                faceOrder[i] = order[i];
                packed |= order[i] << (3 * i);
            }
            tracerCompute.SetInt("_FaceOrderPacked", packed);
        }

        private void BindFrontToMaterial()
        {
            Snapshot front = snapshots[frontIndex];
            targetMaterial.SetTexture("_EventCube", front.Event);
            targetMaterial.SetTexture("_EscapeDirCube", front.EscapeDir);
            targetMaterial.SetTexture("_DiskOrder0Cube", front.Disk0);
            targetMaterial.SetTexture("_DiskOrder1Cube", front.Disk1);
            targetMaterial.SetTexture("_DiskOrder0RedshiftCube", front.Redshift0);
            targetMaterial.SetTexture("_DiskOrder1RedshiftCube", front.Redshift1);
            targetMaterial.SetVector("_ObsEInf", front.EInf);
            targetMaterial.SetFloat("_RoamBlend", 0.0f);
            targetMaterial.SetFloat("_LensRObs", front.RadiusM);
            targetMaterial.SetFloat("_UseFullSkyTransfer", 1.0f);
            targetMaterial.SetFloat("_UseDiskTransfer", 1.0f);
            targetMaterial.SetFloat("_UseDiskCoverageTransfer", 1.0f);
            targetMaterial.SetFloat("_UseAngularWindow", 1.0f);
            targetMaterial.SetFloat("_SkyBlueshift", 1.0f);
            // Live mode stores ABSOLUTE Boyer-Lindquist azimuth in the disk
            // maps (the observer position is baked into each pass), so no
            // observer-azimuth compensation applies - a stale legacy value
            // here would offset the hot spot.
            targetMaterial.SetFloat("_DiskObserverAzimuth", 0.0f);
            // Hot-spot pattern speed is the physical Keplerian Omega at its
            // radius for the CURRENT mass/spin (sign follows the spin, so a
            // spin flip visibly reverses the orbit direction).
            float hotSpotRadius = Mathf.Max(targetMaterial.GetFloat("_DiskHotSpotRadius"), 1.0f);
            targetMaterial.SetFloat(
                "_DiskHotSpotOmega",
                (float)KerrDiskPhysics.KeplerianOmega(mass, spin, hotSpotRadius)
            );
            targetMaterial.DisableKeyword("GRBHXR_ROAM_BLEND");
            // High-resolution window: shown ONLY when its pass origin matches
            // the displayed cube's origin (one exact solution at one position,
            // sampled at two densities). Otherwise the window collapses and
            // the cube covers the whole sky.
            WindowSnapshot frontWindow = windowSnapshots[windowFrontIndex];
            bool showWindow = liveWindowEnabled
                && frontWindow.Valid
                && Mathf.Abs(frontWindow.OriginR - front.OriginR) < 1.0e-6f * Mathf.Max(front.OriginR, 1.0f)
                && Mathf.Abs(frontWindow.OriginTheta - front.OriginTheta) < 1.0e-5f
                && Mathf.Abs(frontWindow.OriginAz - front.OriginAz) < 1.0e-5f
                && frontWindow.OriginMass == front.OriginMass
                && frontWindow.OriginSpin == front.OriginSpin;
            if (showWindow)
            {
                targetMaterial.SetFloat("_UseLiveWindow", 1.0f);
                targetMaterial.SetTexture("_EscapeDirTex", frontWindow.Dir);
                targetMaterial.SetTexture("_EventTex", frontWindow.Event);
                targetMaterial.SetTexture("_WindowDisk0Tex", frontWindow.Disk0);
                targetMaterial.SetTexture("_WindowDisk1Tex", frontWindow.Disk1);
                targetMaterial.SetTexture("_WindowRedshift0Tex", frontWindow.Redshift0);
                targetMaterial.SetTexture("_WindowRedshift1Tex", frontWindow.Redshift1);
                targetMaterial.SetVector(
                    "_LensScreenBounds",
                    new Vector4(
                        -frontWindow.HalfAlpha, frontWindow.HalfAlpha,
                        -frontWindow.HalfAlpha, frontWindow.HalfAlpha
                    )
                );
            }
            else
            {
                targetMaterial.SetFloat("_UseLiveWindow", 0.0f);
                targetMaterial.SetVector("_LensScreenBounds", new Vector4(1.0f, -1.0f, 1.0f, -1.0f));
            }
            // In live mode the map basis is baked from the observer position
            // inside the compute pass; the display applies only the anchor
            // placement rotation.
            var anchor = FindAnyObjectByType<BlackHoleLensAnchorControls>();
            Quaternion rotation = anchor != null ? anchor.transform.rotation : Quaternion.identity;
            targetMaterial.SetVector("_LensWorldRight", rotation * Vector3.right);
            targetMaterial.SetVector("_LensWorldUp", rotation * Vector3.up);
            targetMaterial.SetVector("_LensWorldForward", rotation * Vector3.forward);
        }

        /// <summary>
        /// Computes observer position, tetrad (static outside the ergosphere,
        /// rain inside or when falling), metric rows, basis, and E-inf uniform
        /// for the pass, and uploads them to the compute shader.
        /// </summary>
        /// <summary>
        /// Refuse a pass rather than upload a degraded or NaN observer frame.
        /// The rain construction now throws on the symmetry axis and when the
        /// normalization has no ingoing future-pointing root; previously it
        /// fell back to the static frame, whose 1/sqrt(-g_tt) is NaN inside
        /// the ergosphere. On refusal the previous COMPLETE front snapshot
        /// keeps displaying, which preserves the hard-swap contract.
        /// </summary>
        private bool TryConfigureObserverUniforms(Snapshot snapshot)
        {
            try
            {
                ConfigureObserverUniforms(snapshot);
                observerFrameRefused = false;
                return true;
            }
            catch (InvalidOperationException e)
            {
                if (!observerFrameRefused)
                {
                    observerFrameRefused = true;
                    Debug.LogError($"GR-BH-XR live pass refused: {e.Message}");
                }
                return false;
            }
        }

        private bool observerFrameRefused;

        private void ConfigureObserverUniforms(Snapshot snapshot)
        {
            float radius = Mathf.Max(observerRig.VirtualRadiusM, 0.7f);
            float thetaDeg = observerRig.VirtualThetaDeg;
            float azimuthDeg = observerRig.VirtualAzimuthDeg;
            double theta = thetaDeg * Math.PI / 180.0;
            double azimuth = azimuthDeg * Math.PI / 180.0;
            // CHART DISCIPLINE. The rig tags which chart its azimuth is in and
            // the shift is applied at most once.
            //
            // Grid roam is BL-labelled (every Task 7 keyframe is traced with
            // the observer at BL phi = 0), so the KS Cartesian position needs
            // phi_ks = phi_bl + bl_to_ks_phi_shift(r).
            //
            // Descent playback is ALREADY ingoing Kerr-Schild: the accepted
            // Task 8 manifest documents azimuthDeg as "deg, ingoing
            // Kerr-Schild chart azimuth relative to the first keyframe" and
            // computes it from _phi_tilde = atan2(y r - a x, r x + a y), which
            // is identically phi_ks. Shifting it again put the solver at the
            // wrong worldline point by shift(r) - shift(r_start): -23.2 deg at
            // r = 2.774 M, -91.0 deg at r = 1.644 M and -284.6 deg at the
            // accepted r = 1.4423 M keyframe (M = 1, a = 0.9, r_start = 9 M),
            // i.e. the error diverges exactly where the descent is
            // interesting.
            bool azimuthIsKerrSchild = observerRig.VirtualAzimuthChart
                == BlackHoleObserverRigControls.AzimuthChart.IngoingKerrSchild;
            double phiShift = PhiShiftSafe(radius);
            double phiKs = azimuthIsKerrSchild ? azimuth : azimuth + phiShift;
            double sinT = Math.Sin(theta);
            double[] pos =
            {
                (radius * Math.Cos(phiKs) - spin * Math.Sin(phiKs)) * sinT,
                (radius * Math.Sin(phiKs) + spin * Math.Cos(phiKs)) * sinT,
                radius * Math.Cos(theta),
            };

            double[,] g = KsMetric(pos);
            bool useRain = observerRig.FreeFalling || StaticFrameInvalid(g);
            double[] uVec = useRain ? RainVelocity(pos, g) : StaticVelocity(g);
            double[][] legs = TetradLegs(pos, g, uVec);

            tracerCompute.SetFloat("_MassM", mass);
            tracerCompute.SetFloat("_SpinA", spin);
            tracerCompute.SetFloat("_StepSize", stepSize);
            tracerCompute.SetFloat("_MaxStep", maxStep);
            tracerCompute.SetFloat("_StepRRef", stepRRef);
            tracerCompute.SetInt("_MaxSteps", maxSteps);
            tracerCompute.SetFloat("_MaxLambda", maxLambda);
            tracerCompute.SetFloat("_REscape", rEscape);
            float rPlus = mass + Mathf.Sqrt(Mathf.Max(mass * mass - spin * spin, 0.0f));
            float rMinus = mass - Mathf.Sqrt(Mathf.Max(mass * mass - spin * spin, 0.0f));
            bool interior = radius < rPlus;
            bool pastTracing = useRain;
            tracerCompute.SetFloat("_TimeOrientation", pastTracing ? -1.0f : 1.0f);
            tracerCompute.SetFloat("_CaptureR", CaptureRadius(pastTracing));
            // Validity is the Hamiltonian residual only. The _HugMinR /
            // _HugLambda heuristics are GONE: _HugMinR compared the launch
            // radius against r_+ + 0.05 M and blanked every escaping ray for
            // any observer below that, and _HugLambda both admitted destroyed
            // rays and darkened healthy ones.
            tracerCompute.SetFloat("_HamiltonianMax", hamiltonianMax);
            tracerCompute.SetFloat("_DiskRIn", (float)IscoRadius());
            tracerCompute.SetFloat("_DiskROut", 30.0f * mass);
            tracerCompute.SetInt("_FaceSize", snapshot.Size);
            tracerCompute.SetVector("_ObserverPosition", new Vector4((float)pos[0], (float)pos[1], (float)pos[2], 0.0f));
            tracerCompute.SetVector("_TetradTime", ToVector(uVec));
            tracerCompute.SetVector("_TetradR", ToVector(legs[0]));
            tracerCompute.SetVector("_TetradTheta", ToVector(legs[1]));
            tracerCompute.SetVector("_TetradPhi", ToVector(legs[2]));
            for (int row = 0; row < 4; row += 1)
            {
                tracerCompute.SetVector(
                    $"_ObsMetricRow{row}",
                    new Vector4((float)g[row, 0], (float)g[row, 1], (float)g[row, 2], (float)g[row, 3])
                );
            }
            double phiBl = azimuthIsKerrSchild ? azimuth - phiShift : azimuth;
            ObserverBasisBh(theta, phiBl, out double[] right, out double[] up, out double[] forward);
            tracerCompute.SetVector("_BasisRightBh", new Vector4((float)right[0], (float)right[1], (float)right[2], 0.0f));
            tracerCompute.SetVector("_BasisUpBh", new Vector4((float)up[0], (float)up[1], (float)up[2], 0.0f));
            tracerCompute.SetVector("_BasisForwardBh", new Vector4((float)forward[0], (float)forward[1], (float)forward[2], 0.0f));

            // Per-pixel observer factor uniform: E_inf(d) = w + dot(d, xyz)
            // with covector t-components (sign convention locked against the
            // traced conserved q_t in the Python validation).
            double ut = Row0Dot(g, uVec);
            double etR = Row0Dot(g, legs[0]);
            double etTheta = Row0Dot(g, legs[1]);
            double etPhi = Row0Dot(g, legs[2]);
            snapshot.EInf = new Vector4((float)(-etPhi), (float)(-etTheta), (float)(-etR), (float)(-ut));
        }

        // -------------------------------------------------------------------
        // Kerr-Schild math (C# ports of the audited Python formulas)
        // -------------------------------------------------------------------

        /// <summary>
        /// Observer-position BH-frame basis, the C# form of the accepted
        /// `unity_basis_from_inclination` generalized off `phi_bl = 0`.
        ///
        /// `unity_basis_from_inclination(theta)` builds the basis from the
        /// BL-SPHERICAL observer direction
        /// `(sin th cos phi_bl, sin th sin phi_bl, cos th)` with
        /// `forward = -observer`, `up` the spin-axis projection of forward and
        /// `right = up x forward`; `_bh_to_unity` then dots the escaped
        /// BH-frame momentum against exactly those three vectors. So this is
        /// the ONLY construction the escape directions are consistent with.
        ///
        /// SIGN, and why it is not the kernel's. This is the POSITION-SPACE
        /// role and it carries the OPPOSITE sign to the momentum rotation. The
        /// KS Cartesian azimuth of the observer is
        /// `phi_bl + atan2(a, r) + shift(r)`, so recovering a BH-frame
        /// direction from the KS position is a `-delta` rotation, whereas
        /// `batch_escape_directions` rotates the outgoing MOMENTUM direction
        /// by `+delta` - its docstring records that the two offsets have
        /// opposite signs and that `-delta` on the momentum is worse than no
        /// rotation at all. Copying the momentum sign into this role rotates
        /// the whole sky by `2|delta|`: 1.20 deg at r = 30 M, 5.48 deg at
        /// r = 5 M and 62.1 deg at r = 2 M for a = 0.9 M.
        ///
        /// Taking `phi_bl` from the chart-tagged rig azimuth and building the
        /// direction directly - rather than un-rotating the KS Cartesian
        /// position by `-delta` - also removes a polar-angle error. The KS
        /// embedding carries `sqrt(r^2 + a^2)` in the equatorial component, so
        /// un-rotating recovers polar angle
        /// `atan2(sqrt(r^2 + a^2) sin th, r cos th)` rather than `th`: off by
        /// 0.394 deg at r = 5 M and 2.23 deg at r = 2 M, larger than the
        /// azimuthal offset the rotation existed to remove.
        ///
        /// `theta` and `phiBl` are radians.
        /// </summary>
        private static void ObserverBasisBh(
            double theta,
            double phiBl,
            out double[] right,
            out double[] up,
            out double[] forward
        )
        {
            double sinT = Math.Sin(theta);
            double[] observerBh = { sinT * Math.Cos(phiBl), sinT * Math.Sin(phiBl), Math.Cos(theta) };
            double obsLen = Math.Sqrt(
                observerBh[0] * observerBh[0] + observerBh[1] * observerBh[1] + observerBh[2] * observerBh[2]
            );
            if (obsLen < 1.0e-12)
            {
                throw new InvalidOperationException(
                    "Observer direction degenerated while building the BH basis.");
            }
            forward = new[] { -observerBh[0] / obsLen, -observerBh[1] / obsLen, -observerBh[2] / obsLen };
            double[] spinAxis = { 0.0, 0.0, 1.0 };
            double dotSF = spinAxis[0] * forward[0] + spinAxis[1] * forward[1] + spinAxis[2] * forward[2];
            up = new[]
            {
                spinAxis[0] - dotSF * forward[0],
                spinAxis[1] - dotSF * forward[1],
                spinAxis[2] - dotSF * forward[2],
            };
            double upLen = Math.Sqrt(up[0] * up[0] + up[1] * up[1] + up[2] * up[2]);
            if (upLen < 1.0e-10)
            {
                // On the spin axis `forward` is parallel to it; fall back
                // exactly as `unity_basis_from_inclination` does.
                double[] fallback = { 1.0, 0.0, 0.0 };
                double dotFF = fallback[0] * forward[0] + fallback[1] * forward[1] + fallback[2] * forward[2];
                up = new[]
                {
                    fallback[0] - dotFF * forward[0],
                    fallback[1] - dotFF * forward[1],
                    fallback[2] - dotFF * forward[2],
                };
                upLen = Math.Sqrt(up[0] * up[0] + up[1] * up[1] + up[2] * up[2]);
            }
            up = new[] { up[0] / upLen, up[1] / upLen, up[2] / upLen };
            right = new[]
            {
                up[1] * forward[2] - up[2] * forward[1],
                up[2] * forward[0] - up[0] * forward[2],
                up[0] * forward[1] - up[1] * forward[0],
            };
            double rightLen = Math.Sqrt(right[0] * right[0] + right[1] * right[1] + right[2] * right[2]);
            right = new[] { right[0] / rightLen, right[1] / rightLen, right[2] / rightLen };
            // Re-orthogonalize `up` from the normalized `right`, matching the
            // accepted construction's final `up = forward x right`.
            up = new[]
            {
                forward[1] * right[2] - forward[2] * right[1],
                forward[2] * right[0] - forward[0] * right[2],
                forward[0] * right[1] - forward[1] * right[0],
            };
        }

        private double PhiShiftSafe(double r)
        {
            double rPlus = mass + Math.Sqrt(Math.Max(mass * mass - spin * spin, 0.0));
            double rMinus = mass - Math.Sqrt(Math.Max(mass * mass - spin * spin, 0.0));
            double gap = Math.Max(rPlus - rMinus, 1.0e-6);
            double ratio = Math.Abs((r - rPlus) / Math.Max(Math.Abs(r - rMinus), 1.0e-9));
            return spin / gap * Math.Log(Math.Max(ratio, 1.0e-12));
        }

        private double KsRadiusOf(double[] pos)
        {
            double a2 = spin * spin;
            double rho2 = pos[0] * pos[0] + pos[1] * pos[1] + pos[2] * pos[2];
            double q = rho2 - a2;
            double r2 = 0.5 * (q + Math.Sqrt(q * q + 4.0 * a2 * pos[2] * pos[2]));
            return Math.Sqrt(Math.Max(r2, 0.0));
        }

        private double[,] KsMetric(double[] pos)
        {
            double r = KsRadiusOf(pos);
            double a2 = spin * spin;
            double den = r * r + a2;
            double hden = r * r * r * r + a2 * pos[2] * pos[2];
            double h = mass * r * r * r / hden;
            double[] l = { 1.0, (r * pos[0] + spin * pos[1]) / den, (r * pos[1] - spin * pos[0]) / den, pos[2] / r };
            var g = new double[4, 4];
            for (int i = 0; i < 4; i += 1)
            {
                for (int j = 0; j < 4; j += 1)
                {
                    double eta = i == j ? (i == 0 ? -1.0 : 1.0) : 0.0;
                    g[i, j] = eta + 2.0 * h * l[i] * l[j];
                }
            }
            return g;
        }

        private static bool StaticFrameInvalid(double[,] g)
        {
            return g[0, 0] >= -1.0e-4;  // at/inside the ergosphere
        }

        private static double[] StaticVelocity(double[,] g)
        {
            double factor = 1.0 / Math.Sqrt(-g[0, 0]);
            return new[] { factor, 0.0, 0.0, 0.0 };
        }

        private double[] RainVelocity(double[] pos, double[,] g)
        {
            // Constraints: (g u)_t = -1; axial L = -y (g u)_x + x (g u)_y = 0;
            // theta constant: r u^z - z (grad r . u_spatial) = 0.
            double r = KsRadiusOf(pos);
            // The rain constraint system loses rank on the symmetry axis: both
            // the axial-Killing row and the polar row vanish identically there.
            // Off axis the condition number grows like 6 / theta, so the
            // velocity error scales as 2e-16 / theta. Refuse rather than return
            // a silently degraded frame. Mirrors
            // gr_bh_xr.observers.RAIN_MIN_SIN_THETA.
            double rhoAxis = Math.Sqrt(pos[0] * pos[0] + pos[1] * pos[1]);
            if (rhoAxis <= RainMinSinTheta * r)
            {
                throw new InvalidOperationException(
                    "Rain frame is undefined on the Kerr symmetry axis: the constraint " +
                    $"system loses rank there (sin(theta) ~ {rhoAxis / r:E3} <= {RainMinSinTheta:E1}).");
            }
            double a2 = spin * spin;
            double rho2 = pos[0] * pos[0] + pos[1] * pos[1] + pos[2] * pos[2];
            double gradDen = 2.0 * r * r - rho2 + a2;
            double[] gradR =
            {
                pos[0] * r / gradDen,
                pos[1] * r / gradDen,
                pos[2] * (r * r + a2) / (r * gradDen),
            };
            var c = new double[3, 4];
            var b = new double[3];
            for (int j = 0; j < 4; j += 1)
            {
                c[0, j] = g[0, j];
                c[1, j] = -pos[1] * g[1, j] + pos[0] * g[2, j];
            }
            b[0] = -1.0;
            b[1] = 0.0;
            c[2, 1] = -pos[2] * gradR[0];
            c[2, 2] = -pos[2] * gradR[1];
            c[2, 3] = r - pos[2] * gradR[2];
            b[2] = 0.0;

            // Null direction via the generalized (Levi-Civita) cross product.
            double[] n = GeneralizedCross(c);
            // Particular solution: solve [c; n] u0 = [b; 0].
            var m4 = new double[4, 5];
            for (int i = 0; i < 3; i += 1)
            {
                for (int j = 0; j < 4; j += 1)
                {
                    m4[i, j] = c[i, j];
                }
                m4[i, 4] = b[i];
            }
            for (int j = 0; j < 4; j += 1)
            {
                m4[3, j] = n[j];
            }
            m4[3, 4] = 0.0;
            double[] u0 = Solve4(m4);

            double qa = Quad(g, n, n);
            double qb = 2.0 * Quad(g, u0, n);
            double qc = Quad(g, u0, u0) + 1.0;
            double discriminant = qb * qb - 4.0 * qa * qc;
            if (discriminant < 0.0)
            {
                throw new InvalidOperationException(
                    "Rain velocity normalization has no real solution here.");
            }
            // Vieta-stable roots, mirroring gr_bh_xr.observers.kerr_rain_velocity_ks.
            // The outgoing rain branch diverges as Delta -> 0 in the ingoing
            // chart, which drives qa to zero EXACTLY at r_+. The naive
            // (-qb -/+ sqrt(disc)) / (2 qa) form then divides a catastrophically
            // cancelled numerator by a near-zero denominator and returns a
            // vector that is not a unit timelike four-velocity at all: measured
            // |u.u + 1| = 0.876 at a/M = 0.9 and 5.26 at a/M = 0.998, silently,
            // with no exception. The stable form never subtracts nearly equal
            // quantities. Accepted-main regression:
            // tests/test_observers.py::test_rain_velocity_is_stable_exactly_on_the_outer_horizon.
            double sqrtDisc = Math.Sqrt(discriminant);
            double signB = qb != 0.0 ? Math.Sign(qb) : 1.0;
            double helper = -0.5 * (qb + signB * sqrtDisc);
            var candidates = new System.Collections.Generic.List<double>(2);
            if (helper != 0.0) { candidates.Add(qc / helper); }
            if (qa != 0.0) { candidates.Add(helper / qa); }
            foreach (double root in candidates)
            {
                var u = new double[4];
                for (int j = 0; j < 4; j += 1)
                {
                    u[j] = u0[j] + root * n[j];
                }
                double drTau = gradR[0] * u[1] + gradR[1] * u[2] + gradR[2] * u[3];
                // Ingoing and future-pointing. g^tt = -(1 + 2H) < 0 everywhere
                // in the ingoing chart, so u^t > 0 is a valid causal test on
                // both sides of the outer horizon.
                if (drTau < 0.0 && u[0] > 0.0)
                {
                    return u;
                }
            }
            // NEVER silently fall back to the static frame: StaticVelocity
            // evaluates 1/sqrt(-g_tt), which is NaN inside the ergosphere, so
            // the old fallback uploaded a NaN tetrad to the GPU rather than
            // failing. Refuse the pass instead.
            throw new InvalidOperationException(
                "No ingoing future-pointing rain solution found.");
        }

        private double[][] TetradLegs(double[] pos, double[,] g, double[] uVec)
        {
            double r = KsRadiusOf(pos);
            double a2 = spin * spin;
            double rho2 = pos[0] * pos[0] + pos[1] * pos[1] + pos[2] * pos[2];
            double gradDen = 2.0 * r * r - rho2 + a2;
            double[] radial = { 0.0, pos[0] * r / gradDen, pos[1] * r / gradDen, pos[2] * (r * r + a2) / (r * gradDen) };
            double[] phiLeg = { 0.0, -pos[1], pos[0], 0.0 };
            double cosT = pos[2] / r;
            // sin(theta) = rho / r, matching gr_bh_xr.observers.kerr_rain_tetrad_ks
            // exactly. The sqrt(max(1 - cos^2, 1e-16)) form is a DIFFERENT
            // quantity - it is the Boyer-Lindquist sin(theta), smaller by
            // sqrt(1 + a^2/r^2) - and it additionally floors silently near the
            // axis, producing a mis-oriented e_theta that still orthonormalizes
            // perfectly, so no Gram check can detect it. The systematic leg
            // rotation reaches 11.7 deg at the accepted near-horizon keyframe
            // r = 1.4423 M, far above the comparator's 0.05 deg direction gate.
            double rhoCyl = Math.Sqrt(pos[0] * pos[0] + pos[1] * pos[1]);
            double sinT = rhoCyl / r;
            double[] thetaLeg = { 0.0, pos[0] * cosT / sinT, pos[1] * cosT / sinT, -r * sinT };

            double[] ePhi = ProjectNormalize(g, phiLeg, new[] { uVec });
            double[] eTheta = ProjectNormalize(g, thetaLeg, new[] { uVec, ePhi });
            double[] eR = ProjectNormalize(g, radial, new[] { uVec, ePhi, eTheta });
            return new[] { eR, eTheta, ePhi };
        }

        private static double[] ProjectNormalize(double[,] g, double[] candidate, double[][] against)
        {
            var v = (double[])candidate.Clone();
            foreach (double[] basis in against)
            {
                double norm = Quad(g, basis, basis);
                double coefficient = Quad(g, v, basis) / norm;
                for (int j = 0; j < 4; j += 1)
                {
                    v[j] -= coefficient * basis[j];
                }
            }
            double length = Math.Sqrt(Quad(g, v, v));
            for (int j = 0; j < 4; j += 1)
            {
                v[j] /= length;
            }
            return v;
        }

        private static double Quad(double[,] g, double[] u, double[] v)
        {
            double total = 0.0;
            for (int i = 0; i < 4; i += 1)
            {
                for (int j = 0; j < 4; j += 1)
                {
                    total += g[i, j] * u[i] * v[j];
                }
            }
            return total;
        }

        private static double Row0Dot(double[,] g, double[] v)
        {
            return g[0, 0] * v[0] + g[0, 1] * v[1] + g[0, 2] * v[2] + g[0, 3] * v[3];
        }

        private static double[] GeneralizedCross(double[,] c)
        {
            // n_mu = det of the 3x3 minor with column mu removed, alternating sign.
            var n = new double[4];
            for (int mu = 0; mu < 4; mu += 1)
            {
                var minor = new double[3, 3];
                for (int i = 0; i < 3; i += 1)
                {
                    int col = 0;
                    for (int j = 0; j < 4; j += 1)
                    {
                        if (j == mu)
                        {
                            continue;
                        }
                        minor[i, col] = c[i, j];
                        col += 1;
                    }
                }
                double det =
                    minor[0, 0] * (minor[1, 1] * minor[2, 2] - minor[1, 2] * minor[2, 1])
                    - minor[0, 1] * (minor[1, 0] * minor[2, 2] - minor[1, 2] * minor[2, 0])
                    + minor[0, 2] * (minor[1, 0] * minor[2, 1] - minor[1, 1] * minor[2, 0]);
                n[mu] = (mu % 2 == 0 ? 1.0 : -1.0) * det;
            }
            return n;
        }

        private static double[] Solve4(double[,] augmented)
        {
            // Gaussian elimination with partial pivoting on a 4x5 system.
            for (int pivot = 0; pivot < 4; pivot += 1)
            {
                int best = pivot;
                for (int row = pivot + 1; row < 4; row += 1)
                {
                    if (Math.Abs(augmented[row, pivot]) > Math.Abs(augmented[best, pivot]))
                    {
                        best = row;
                    }
                }
                if (best != pivot)
                {
                    for (int col = 0; col < 5; col += 1)
                    {
                        (augmented[pivot, col], augmented[best, col]) = (augmented[best, col], augmented[pivot, col]);
                    }
                }
                double diag = augmented[pivot, pivot];
                for (int row = pivot + 1; row < 4; row += 1)
                {
                    double factor = augmented[row, pivot] / diag;
                    for (int col = pivot; col < 5; col += 1)
                    {
                        augmented[row, col] -= factor * augmented[pivot, col];
                    }
                }
            }
            var solution = new double[4];
            for (int row = 3; row >= 0; row -= 1)
            {
                double sum = augmented[row, 4];
                for (int col = row + 1; col < 4; col += 1)
                {
                    sum -= augmented[row, col] * solution[col];
                }
                solution[row] = sum / augmented[row, row];
            }
            return solution;
        }

        private double IscoRadius()
        {
            // Co-rotating BPT ISCO (shared with the live disk LUT physics).
            return KerrDiskPhysics.IscoRadius(mass, spin);
        }

        private static Vector4 ToVector(double[] v)
        {
            return new Vector4((float)v[0], (float)v[1], (float)v[2], (float)v[3]);
        }

        private void EnsureSnapshotTextures(Snapshot snapshot, int size)
        {
            if (snapshot.EscapeDir != null && snapshot.Size == size)
            {
                return;
            }
            ReleaseSnapshot(snapshot);
            snapshot.Size = size;
            snapshot.StagingEscapeDir = NewTexture(size, RenderTextureFormat.ARGBFloat, cube: false);
            snapshot.StagingEvent = NewTexture(size, RenderTextureFormat.ARGB32, cube: false);
            snapshot.StagingDisk0 = NewTexture(size, RenderTextureFormat.ARGBHalf, cube: false);
            snapshot.StagingDisk1 = NewTexture(size, RenderTextureFormat.ARGBHalf, cube: false);
            snapshot.StagingRedshift0 = NewTexture(size, RenderTextureFormat.ARGBHalf, cube: false);
            snapshot.StagingRedshift1 = NewTexture(size, RenderTextureFormat.ARGBHalf, cube: false);
            snapshot.EscapeDir = NewTexture(size, RenderTextureFormat.ARGBFloat, cube: true);
            snapshot.Event = NewTexture(size, RenderTextureFormat.ARGB32, cube: true);
            snapshot.Disk0 = NewTexture(size, RenderTextureFormat.ARGBHalf, cube: true);
            snapshot.Disk1 = NewTexture(size, RenderTextureFormat.ARGBHalf, cube: true);
            snapshot.Redshift0 = NewTexture(size, RenderTextureFormat.ARGBHalf, cube: true);
            snapshot.Redshift1 = NewTexture(size, RenderTextureFormat.ARGBHalf, cube: true);
        }

        private void EnsureEventMaskBuffer(int size)
        {
            int count = size * size * 6;
            if (eventMaskBuffer != null && eventMaskBuffer.count == count)
            {
                return;
            }
            eventMaskBuffer?.Release();
            eventMaskBuffer = new ComputeBuffer(count, sizeof(uint));
            // Audit buffers share the mask's length and lifetime. They are
            // written by the trace kernel and read only by the validation
            // dump; the display path never touches them.
            classBuffer?.Release();
            classBuffer = new ComputeBuffer(count, sizeof(uint));
            hMaxBuffer?.Release();
            hMaxBuffer = new ComputeBuffer(count, sizeof(float));
        }

        private void EnsureWindowTextures(WindowSnapshot snapshot, int size)
        {
            if (snapshot.Dir != null && snapshot.Size == size)
            {
                return;
            }
            ReleaseWindowSnapshot(snapshot);
            snapshot.Size = size;
            snapshot.Dir = NewWindowTexture(size, RenderTextureFormat.ARGBFloat);
            snapshot.Event = NewWindowTexture(size, RenderTextureFormat.ARGB32);
            snapshot.Disk0 = NewWindowTexture(size, RenderTextureFormat.ARGBHalf);
            snapshot.Disk1 = NewWindowTexture(size, RenderTextureFormat.ARGBHalf);
            snapshot.Redshift0 = NewWindowTexture(size, RenderTextureFormat.ARGBHalf);
            snapshot.Redshift1 = NewWindowTexture(size, RenderTextureFormat.ARGBHalf);
        }

        private RenderTexture NewWindowTexture(int size, RenderTextureFormat format)
        {
            var texture = new RenderTexture(size, size, 0, format)
            {
                enableRandomWrite = true,
                useMipMap = false,
                wrapMode = TextureWrapMode.Clamp,
                filterMode = FilterMode.Bilinear,
                hideFlags = HideFlags.DontSave,
            };
            texture.Create();
            return texture;
        }

        private void EnsureWindowMaskBuffer(int size)
        {
            int count = size * size;
            if (windowMaskBuffer != null && windowMaskBuffer.count == count)
            {
                return;
            }
            windowMaskBuffer?.Release();
            windowMaskBuffer = new ComputeBuffer(count, sizeof(uint));
        }

        private void BindWindowOutputs(int kernelIndex, WindowSnapshot snapshot)
        {
            tracerCompute.SetTexture(kernelIndex, "_OutWinEscapeDir", snapshot.Dir);
            tracerCompute.SetTexture(kernelIndex, "_OutWinEvent", snapshot.Event);
            tracerCompute.SetTexture(kernelIndex, "_OutWinDisk0", snapshot.Disk0);
            tracerCompute.SetTexture(kernelIndex, "_OutWinDisk1", snapshot.Disk1);
            tracerCompute.SetTexture(kernelIndex, "_OutWinRedshift0", snapshot.Redshift0);
            tracerCompute.SetTexture(kernelIndex, "_OutWinRedshift1", snapshot.Redshift1);
            tracerCompute.SetBuffer(kernelIndex, "_WinEventMask", windowMaskBuffer);
        }

        private static void ReleaseWindowSnapshot(WindowSnapshot snapshot)
        {
            ReleaseTexture(ref snapshot.Dir);
            ReleaseTexture(ref snapshot.Event);
            ReleaseTexture(ref snapshot.Disk0);
            ReleaseTexture(ref snapshot.Disk1);
            ReleaseTexture(ref snapshot.Redshift0);
            ReleaseTexture(ref snapshot.Redshift1);
            snapshot.Valid = false;
        }

        private RenderTexture NewTexture(int size, RenderTextureFormat format, bool cube)
        {
            var texture = new RenderTexture(size, size, 0, format)
            {
                dimension = cube
                    ? UnityEngine.Rendering.TextureDimension.Cube
                    : UnityEngine.Rendering.TextureDimension.Tex2DArray,
                volumeDepth = cube ? 1 : 6,
                enableRandomWrite = !cube,
                useMipMap = false,
                wrapMode = TextureWrapMode.Clamp,
                filterMode = FilterMode.Bilinear,
                hideFlags = HideFlags.DontSave,
            };
            texture.Create();
            return texture;
        }

        private void BindOutputs(int kernelIndex, Snapshot snapshot)
        {
            tracerCompute.SetTexture(kernelIndex, "_OutEscapeDir", snapshot.StagingEscapeDir);
            tracerCompute.SetTexture(kernelIndex, "_OutEvent", snapshot.StagingEvent);
            tracerCompute.SetTexture(kernelIndex, "_OutDisk0", snapshot.StagingDisk0);
            tracerCompute.SetTexture(kernelIndex, "_OutDisk1", snapshot.StagingDisk1);
            tracerCompute.SetTexture(kernelIndex, "_OutRedshift0", snapshot.StagingRedshift0);
            tracerCompute.SetTexture(kernelIndex, "_OutRedshift1", snapshot.StagingRedshift1);
            tracerCompute.SetBuffer(kernelIndex, "_EventMask", eventMaskBuffer);
            tracerCompute.SetBuffer(kernelIndex, "_ClassBuffer", classBuffer);
            tracerCompute.SetBuffer(kernelIndex, "_HMaxBuffer", hMaxBuffer);
        }

        private void OnDestroy()
        {
            foreach (Snapshot snapshot in snapshots)
            {
                ReleaseSnapshot(snapshot);
            }
            foreach (WindowSnapshot snapshot in windowSnapshots)
            {
                ReleaseWindowSnapshot(snapshot);
            }
            eventMaskBuffer?.Release();
            eventMaskBuffer = null;
            classBuffer?.Release();
            classBuffer = null;
            hMaxBuffer?.Release();
            hMaxBuffer = null;
            windowMaskBuffer?.Release();
            windowMaskBuffer = null;
            if (diskRadialLutTexture != null)
            {
                Destroy(diskRadialLutTexture);
                diskRadialLutTexture = null;
            }
        }

        private static void ReleaseSnapshot(Snapshot snapshot)
        {
            ReleaseTexture(ref snapshot.StagingEscapeDir);
            ReleaseTexture(ref snapshot.StagingEvent);
            ReleaseTexture(ref snapshot.StagingDisk0);
            ReleaseTexture(ref snapshot.StagingDisk1);
            ReleaseTexture(ref snapshot.StagingRedshift0);
            ReleaseTexture(ref snapshot.StagingRedshift1);
            ReleaseTexture(ref snapshot.EscapeDir);
            ReleaseTexture(ref snapshot.Event);
            ReleaseTexture(ref snapshot.Disk0);
            ReleaseTexture(ref snapshot.Disk1);
            ReleaseTexture(ref snapshot.Redshift0);
            ReleaseTexture(ref snapshot.Redshift1);
            snapshot.Valid = false;
        }

        private static void ReleaseTexture(ref RenderTexture texture)
        {
            if (texture != null)
            {
                texture.Release();
                texture = null;
            }
        }

        /// <summary>
        /// Synchronous full-sky pass at an explicit observer state, dumped to
        /// raw files plus a metadata JSON carrying the exact tetrad used, so
        /// the Python wgpu tracer can re-trace the same rays and compare
        /// texel-wise (the repo's CPU/GPU cross-check pattern).
        /// </summary>
        public void ValidationDump(string outputDirectory, float radiusM, float thetaDeg, bool rainFrame)
        {
            ValidationDump(outputDirectory, radiusM, thetaDeg, rainFrame, rEscape);
        }

        /// <summary>
        /// Dump at an explicit escape radius (geometric length, same unit as M).
        ///
        /// This exists so the gate can emit the MULTI-r_escape dump set. The
        /// escaped-momentum chart correction is
        /// `2|delta| = 2|atan2(a, r) + bl_to_ks_phi_shift(r)| ~ 2 a M / r^2`,
        /// which for a = 0.9 M is 2.60e-3 deg at r_escape = 200 M - only about
        /// 8x the measured f32 agreement floor of 3.25e-4 deg, i.e. the sign is
        /// resolved with almost no margin. The same dump at 100 M and 50 M
        /// widens the correction to 1.05e-2 and 4.24e-2 deg, so the sign gate
        /// has 4x and 16x more room. A dump set that only ever runs far out is
        /// one f32 regression away from being unable to see the sign at all.
        /// </summary>
        public void ValidationDump(
            string outputDirectory, float radiusM, float thetaDeg, bool rainFrame, float rEscapeOverrideM)
        {
            if (rEscapeOverrideM <= 0.0f || !float.IsFinite(rEscapeOverrideM))
            {
                throw new ArgumentOutOfRangeException(
                    nameof(rEscapeOverrideM),
                    "Escape radius must be a positive geometric length.");
            }
            float savedREscape = rEscape;
            rEscape = rEscapeOverrideM;
            try
            {
                ValidationDumpAtCurrentEscapeRadius(outputDirectory, radiusM, thetaDeg, rainFrame);
            }
            finally
            {
                rEscape = savedREscape;
            }
        }

        private void ValidationDumpAtCurrentEscapeRadius(
            string outputDirectory, float radiusM, float thetaDeg, bool rainFrame)
        {
            if (tracerCompute == null)
            {
                throw new InvalidOperationException("tracerCompute not assigned.");
            }
            if (kernel < 0)
            {
                kernel = tracerCompute.FindKernel("TraceTexels");
                refineKernel = tracerCompute.FindKernel("RefineTexels");
            }
            System.IO.Directory.CreateDirectory(outputDirectory);

            RenderTexture NewArray(RenderTextureFormat format)
            {
                var texture = new RenderTexture(faceSize, faceSize, 0, format)
                {
                    dimension = UnityEngine.Rendering.TextureDimension.Tex2DArray,
                    volumeDepth = 6,
                    enableRandomWrite = true,
                    useMipMap = false,
                };
                texture.Create();
                return texture;
            }

            RenderTexture dir = NewArray(RenderTextureFormat.ARGBFloat);
            RenderTexture evt = NewArray(RenderTextureFormat.ARGB32);
            RenderTexture d0 = NewArray(RenderTextureFormat.ARGBFloat);
            RenderTexture d1 = NewArray(RenderTextureFormat.ARGBFloat);
            RenderTexture r0 = NewArray(RenderTextureFormat.ARGBFloat);
            RenderTexture r1 = NewArray(RenderTextureFormat.ARGBFloat);

            var stub = new Snapshot();
            // Drive the uniforms from an explicit state instead of the rig.
            float savedRadius = observerRig != null ? observerRig.VirtualRadiusM : -1.0f;
            var metadata = ConfigureValidationUniforms(stub, radiusM, thetaDeg, rainFrame);

            int totalTexels = faceSize * faceSize * 6;
            var mask = new ComputeBuffer(totalTexels, sizeof(uint));
            // Structured classification for the scientific artifact. The
            // display may render every non-escape class dark; the dump and
            // the comparator must be able to tell physical capture from a
            // non-finite RK state from affine-budget exhaustion.
            var classes = new ComputeBuffer(totalTexels, sizeof(uint));
            var hMaxes = new ComputeBuffer(totalTexels, sizeof(float));
            tracerCompute.SetTexture(kernel, "_OutEscapeDir", dir);
            tracerCompute.SetTexture(kernel, "_OutEvent", evt);
            tracerCompute.SetTexture(kernel, "_OutDisk0", d0);
            tracerCompute.SetTexture(kernel, "_OutDisk1", d1);
            tracerCompute.SetTexture(kernel, "_OutRedshift0", r0);
            tracerCompute.SetTexture(kernel, "_OutRedshift1", r1);
            tracerCompute.SetBuffer(kernel, "_EventMask", mask);
            tracerCompute.SetBuffer(kernel, "_ClassBuffer", classes);
            tracerCompute.SetBuffer(kernel, "_HMaxBuffer", hMaxes);
            tracerCompute.SetInt("_TexelBase", 0);
            tracerCompute.SetInt("_TexelCount", totalTexels);
            tracerCompute.Dispatch(kernel, Mathf.CeilToInt(totalTexels / 64.0f), 1, 1);

            DumpArray(dir, System.IO.Path.Combine(outputDirectory, "live_escape_dir_rgba32f.bytes"));
            DumpArray(d0, System.IO.Path.Combine(outputDirectory, "live_disk0_rgba32f.bytes"));
            DumpArray(r0, System.IO.Path.Combine(outputDirectory, "live_redshift0_rgba32f.bytes"));

            // Limb-refine stage on top of the same textures: dump the event
            // mask plus the refined maps so Python can re-trace the 3x3
            // subrays of every limb texel and compare fractional coverage.
            tracerCompute.SetTexture(refineKernel, "_OutEscapeDir", dir);
            tracerCompute.SetTexture(refineKernel, "_OutEvent", evt);
            tracerCompute.SetTexture(refineKernel, "_OutDisk0", d0);
            tracerCompute.SetTexture(refineKernel, "_OutDisk1", d1);
            tracerCompute.SetTexture(refineKernel, "_OutRedshift0", r0);
            tracerCompute.SetTexture(refineKernel, "_OutRedshift1", r1);
            tracerCompute.SetBuffer(refineKernel, "_EventMask", mask);
            tracerCompute.SetBuffer(refineKernel, "_ClassBuffer", classes);
            tracerCompute.SetBuffer(refineKernel, "_HMaxBuffer", hMaxes);
            tracerCompute.Dispatch(refineKernel, Mathf.CeilToInt(totalTexels / 64.0f), 1, 1);

            DumpArray(dir, System.IO.Path.Combine(outputDirectory, "live_escape_dir_refined_rgba32f.bytes"));
            DumpArray(d0, System.IO.Path.Combine(outputDirectory, "live_disk0_refined_rgba32f.bytes"));
            DumpArray(r0, System.IO.Path.Combine(outputDirectory, "live_redshift0_refined_rgba32f.bytes"));

            var maskData = new uint[totalTexels];
            mask.GetData(maskData);
            var maskBytes = new byte[totalTexels * 4];
            Buffer.BlockCopy(maskData, 0, maskBytes, 0, maskBytes.Length);
            System.IO.File.WriteAllBytes(
                System.IO.Path.Combine(outputDirectory, "live_event_mask_u32.bytes"),
                maskBytes
            );

            var classData = new uint[totalTexels];
            classes.GetData(classData);
            var classBytes = new byte[totalTexels * 4];
            Buffer.BlockCopy(classData, 0, classBytes, 0, classBytes.Length);
            System.IO.File.WriteAllBytes(
                System.IO.Path.Combine(outputDirectory, "live_class_u32.bytes"),
                classBytes
            );

            var hMaxData = new float[totalTexels];
            hMaxes.GetData(hMaxData);
            var hMaxBytes = new byte[totalTexels * 4];
            Buffer.BlockCopy(hMaxData, 0, hMaxBytes, 0, hMaxBytes.Length);
            System.IO.File.WriteAllBytes(
                System.IO.Path.Combine(outputDirectory, "live_h_max_abs_f32.bytes"),
                hMaxBytes
            );

            // Angular-window stage: same physics kernel, gnomonic texel ->
            // direction map. Python re-derives the directions from the
            // dumped bounds and re-traces.
            int windowSize = 256;
            float windowHalfAlpha = radiusM * Mathf.Tan(WindowHalfAngleRad(radiusM));
            RenderTexture winDir = NewWindowTexture(windowSize, RenderTextureFormat.ARGBFloat);
            RenderTexture winEvt = NewWindowTexture(windowSize, RenderTextureFormat.ARGB32);
            RenderTexture winD0 = NewWindowTexture(windowSize, RenderTextureFormat.ARGBFloat);
            RenderTexture winD1 = NewWindowTexture(windowSize, RenderTextureFormat.ARGBFloat);
            RenderTexture winR0 = NewWindowTexture(windowSize, RenderTextureFormat.ARGBFloat);
            RenderTexture winR1 = NewWindowTexture(windowSize, RenderTextureFormat.ARGBFloat);
            var winMask = new ComputeBuffer(windowSize * windowSize, sizeof(uint));
            if (windowKernel < 0)
            {
                windowKernel = tracerCompute.FindKernel("TraceWindow");
            }
            tracerCompute.SetInt("_WindowSize", windowSize);
            tracerCompute.SetFloat("_WindowHalfAlpha", windowHalfAlpha);
            tracerCompute.SetFloat("_WindowRObs", radiusM);
            tracerCompute.SetTexture(windowKernel, "_OutWinEscapeDir", winDir);
            tracerCompute.SetTexture(windowKernel, "_OutWinEvent", winEvt);
            tracerCompute.SetTexture(windowKernel, "_OutWinDisk0", winD0);
            tracerCompute.SetTexture(windowKernel, "_OutWinDisk1", winD1);
            tracerCompute.SetTexture(windowKernel, "_OutWinRedshift0", winR0);
            tracerCompute.SetTexture(windowKernel, "_OutWinRedshift1", winR1);
            tracerCompute.SetBuffer(windowKernel, "_WinEventMask", winMask);
            int windowTexels = windowSize * windowSize;
            tracerCompute.SetInt("_TexelBase", 0);
            tracerCompute.SetInt("_TexelCount", windowTexels);
            tracerCompute.Dispatch(windowKernel, Mathf.CeilToInt(windowTexels / 64.0f), 1, 1);
            Dump2D(winDir, System.IO.Path.Combine(outputDirectory, "live_window_dir_rgba32f.bytes"));
            Dump2D(winD0, System.IO.Path.Combine(outputDirectory, "live_window_disk0_rgba32f.bytes"));
            Dump2D(winR0, System.IO.Path.Combine(outputDirectory, "live_window_redshift0_rgba32f.bytes"));

            // Window limb-refine stage. Previously never dispatched here, so
            // the RefineWindow kernel shipped entirely unvalidated while the
            // cube-face RefineTexels kernel was gated. Same 3x3 subray
            // fractional-coverage contract as the cube path.
            if (windowRefineKernel < 0)
            {
                windowRefineKernel = tracerCompute.FindKernel("RefineWindow");
            }
            tracerCompute.SetTexture(windowRefineKernel, "_OutWinEscapeDir", winDir);
            tracerCompute.SetTexture(windowRefineKernel, "_OutWinEvent", winEvt);
            tracerCompute.SetTexture(windowRefineKernel, "_OutWinDisk0", winD0);
            tracerCompute.SetTexture(windowRefineKernel, "_OutWinDisk1", winD1);
            tracerCompute.SetTexture(windowRefineKernel, "_OutWinRedshift0", winR0);
            tracerCompute.SetTexture(windowRefineKernel, "_OutWinRedshift1", winR1);
            tracerCompute.SetBuffer(windowRefineKernel, "_WinEventMask", winMask);
            tracerCompute.SetInt("_TexelBase", 0);
            tracerCompute.SetInt("_TexelCount", windowTexels);
            tracerCompute.Dispatch(windowRefineKernel, Mathf.CeilToInt(windowTexels / 64.0f), 1, 1);
            Dump2D(winDir, System.IO.Path.Combine(outputDirectory, "live_window_dir_refined_rgba32f.bytes"));
            Dump2D(winD0, System.IO.Path.Combine(outputDirectory, "live_window_disk0_refined_rgba32f.bytes"));
            Dump2D(winR0, System.IO.Path.Combine(outputDirectory, "live_window_redshift0_refined_rgba32f.bytes"));

            var winMaskData = new uint[windowTexels];
            winMask.GetData(winMaskData);
            var winMaskBytes = new byte[windowTexels * 4];
            Buffer.BlockCopy(winMaskData, 0, winMaskBytes, 0, winMaskBytes.Length);
            System.IO.File.WriteAllBytes(
                System.IO.Path.Combine(outputDirectory, "live_window_mask_u32.bytes"),
                winMaskBytes
            );

            winMask.Release();
            winDir.Release();
            winEvt.Release();
            winD0.Release();
            winD1.Release();
            winR0.Release();
            winR1.Release();

            // Compose the document structurally. `stages` is the contract the
            // Python gate enforces: it must validate every stage listed here,
            // so a dump can never silently omit one and still report PASS.
            string document = "{\n"
                + metadata + ",\n"
                + $"  \"windowSize\": {windowSize}, \"windowHalfAlpha\": {windowHalfAlpha:R}, \"windowRObs\": {radiusM:R},\n"
                + "  \"stages\": [\"main\", \"refine\", \"window\", \"windowRefine\"]\n"
                + "}\n";
            System.IO.File.WriteAllText(
                System.IO.Path.Combine(outputDirectory, "live_tracer_validation.json"),
                document
            );
            mask.Release();
            classes.Release();
            hMaxes.Release();
            dir.Release();
            evt.Release();
            d0.Release();
            d1.Release();
            r0.Release();
            r1.Release();
            Debug.Log(
                $"GR-BH-XR live tracer validation dump: r={radiusM}, theta={thetaDeg}, " +
                $"rain={rainFrame}, faceSize={faceSize} -> {outputDirectory} (saved rig r={savedRadius})."
            );
        }

        private string ConfigureValidationUniforms(Snapshot snapshot, float radiusM, float thetaDeg, bool rainFrame)
        {
            double theta = thetaDeg * Math.PI / 180.0;
            double phiKs = PhiShiftSafe(radiusM);
            double sinT = Math.Sin(theta);
            double[] pos =
            {
                (radiusM * Math.Cos(phiKs) - spin * Math.Sin(phiKs)) * sinT,
                (radiusM * Math.Sin(phiKs) + spin * Math.Cos(phiKs)) * sinT,
                radiusM * Math.Cos(theta),
            };
            double[,] g = KsMetric(pos);
            double[] uVec = rainFrame ? RainVelocity(pos, g) : StaticVelocity(g);
            double[][] legs = TetradLegs(pos, g, uVec);

            tracerCompute.SetFloat("_MassM", mass);
            tracerCompute.SetFloat("_SpinA", spin);
            tracerCompute.SetFloat("_StepSize", stepSize);
            tracerCompute.SetFloat("_MaxStep", maxStep);
            tracerCompute.SetFloat("_StepRRef", stepRRef);
            tracerCompute.SetInt("_MaxSteps", maxSteps);
            tracerCompute.SetFloat("_MaxLambda", maxLambda);
            tracerCompute.SetFloat("_REscape", rEscape);
            float rPlus = mass + Mathf.Sqrt(Mathf.Max(mass * mass - spin * spin, 0.0f));
            float rMinus = mass - Mathf.Sqrt(Mathf.Max(mass * mass - spin * spin, 0.0f));
            float timeOrientation = rainFrame ? -1.0f : 1.0f;
            // Same M-scaled surfaces as the runtime path. The dump previously
            // used bare 0.05 offsets, so at any mass other than 1 the gate
            // compared a Unity termination radius against a Python one that
            // did scale with M - and the comparator's exactness assertion
            // would have failed the run rather than silently disagreeing,
            // which is how this was caught.
            float captureR = CaptureRadius(rainFrame);
            tracerCompute.SetFloat("_HamiltonianMax", hamiltonianMax);
            float diskRIn = (float)IscoRadius();
            // Was a bare 30.0f, which disagreed with the runtime path
            // (30 M, line 745) and with the runtime disk LUT whenever the
            // mass slider left M = 1. The dump must trace the same disk the
            // runtime traces or the cross-check compares two geometries.
            float diskROut = 30.0f * mass;
            tracerCompute.SetFloat("_TimeOrientation", timeOrientation);
            tracerCompute.SetFloat("_CaptureR", captureR);
            tracerCompute.SetFloat("_DiskRIn", diskRIn);
            tracerCompute.SetFloat("_DiskROut", diskROut);
            tracerCompute.SetInt("_FaceSize", faceSize);
            tracerCompute.SetVector("_ObserverPosition", new Vector4((float)pos[0], (float)pos[1], (float)pos[2], 0.0f));
            tracerCompute.SetVector("_TetradTime", ToVector(uVec));
            tracerCompute.SetVector("_TetradR", ToVector(legs[0]));
            tracerCompute.SetVector("_TetradTheta", ToVector(legs[1]));
            tracerCompute.SetVector("_TetradPhi", ToVector(legs[2]));
            for (int row = 0; row < 4; row += 1)
            {
                tracerCompute.SetVector(
                    $"_ObsMetricRow{row}",
                    new Vector4((float)g[row, 0], (float)g[row, 1], (float)g[row, 2], (float)g[row, 3])
                );
            }
            // Identity Unity basis for validation (BH frame dirs dumped raw)
            // and identity face order (the runtime path re-sorts per pass).
            // NOTE: because of this, the traced directions in this dump do NOT
            // exercise the runtime observer basis at all - that role was
            // therefore completely ungated. `observerBasisProbes` below closes
            // it without perturbing the raw-direction contract.
            tracerCompute.SetVector("_BasisRightBh", new Vector4(1, 0, 0, 0));
            tracerCompute.SetVector("_BasisUpBh", new Vector4(0, 1, 0, 0));
            tracerCompute.SetVector("_BasisForwardBh", new Vector4(0, 0, 1, 0));
            int identityOrder = 0;
            for (int i = 0; i < 6; i += 1)
            {
                identityOrder |= i << (3 * i);
            }
            tracerCompute.SetInt("_FaceOrderPacked", identityOrder);

            // Metadata BODY only - no braces. `ValidationDump` composes the
            // object so per-stage keys are appended structurally instead of
            // being spliced into a finished document with a string Replace.
            // Every constant the Python cross-check needs is published here:
            // when a value is hardcoded on both sides independently, the gate
            // stops testing agreement and starts assuming it.
            string Row(double[] v) => $"[{v[0]:R},{v[1]:R},{v[2]:R},{v[3]:R}]";
            return $"  \"faceSize\": {faceSize},\n"
                + $"  \"mass\": {mass:R}, \"spin\": {spin:R},\n"
                + $"  \"radiusM\": {radiusM:R}, \"thetaDeg\": {thetaDeg:R}, \"rainFrame\": {(rainFrame ? "true" : "false")},\n"
                + $"  \"position\": [{pos[0]:R},{pos[1]:R},{pos[2]:R}],\n"
                + $"  \"tetradTime\": {Row(uVec)},\n"
                + $"  \"tetradR\": {Row(legs[0])},\n"
                + $"  \"tetradTheta\": {Row(legs[1])},\n"
                + $"  \"tetradPhi\": {Row(legs[2])},\n"
                + $"  \"stepSize\": {stepSize:R}, \"maxSteps\": {maxSteps}, \"maxLambda\": {maxLambda:R}, \"rEscape\": {rEscape:R},\n"
                + $"  \"maxStep\": {maxStep:R}, \"stepRRef\": {stepRRef:R}, \"adaptiveStep\": true,\n"
                + $"  \"timeOrientation\": {timeOrientation:R},\n"
                + $"  \"captureR\": {captureR:R}, \"hamiltonianMax\": {hamiltonianMax:R},\n"
                + "  \"eventCodes\": {\"capture\": 0, \"escape\": 1, \"disk_crossing\": 2, \"invalid\": 3, \"object_hit\": 4},\n"
                + "  \"failureCodes\": {\"none\": 0, \"trace_exception\": 1, \"unclassified_max_lambda\": 2, \"solver_failure\": 3},\n"
                + "  \"classBits\": {\"eventShift\": 0, \"eventMask\": 15, \"failureShift\": 4, \"failureMask\": 15, \"hamiltonianRejectedBit\": 256},\n"
                + $"  \"diskRIn\": {diskRIn:R}, \"diskROut\": {diskROut:R}, \"diskMaxOrder\": 2,\n"
                + "  \"refineSubrayGrid\": 3, \"refineSubrayOffsetScale\": 0.3333333333333333,\n"
                + $"  \"observerBasisProbes\": {ObserverBasisProbeJson(thetaDeg)},\n"
                + "  \"maskBits\": {\"escape\": 1, \"disk0\": 2, \"disk1\": 4}";
        }

        // Probe grid for the observer-basis gate. Radii are MULTIPLES OF M and
        // are scaled by the live mass below, so the probe stays at the same
        // physical station when the mass slider moves. The azimuths are
        // deliberately non-zero: at phi = 0 the basis is symmetric under
        // phi -> -phi, so a sign error in either the chart conversion or the
        // basis derivation would be invisible.
        private static readonly float[] BasisProbeRadiiOverM = { 30.0f, 10.0f, 5.0f, 3.0f, 2.0f };
        private static readonly float[] BasisProbeAzimuthsDeg = { 0.0f, 37.0f, -122.0f };

        /// <summary>
        /// Publish the runtime observer basis at a grid of (r, azimuth, chart)
        /// stations, built by the SAME code the runtime pass uses.
        ///
        /// This is the only place the C# observer-position role is externally
        /// observable. Each probe runs the chart conversion
        /// (`phi_bl = phi_ks - shift(r)` for a Kerr-Schild-labelled azimuth,
        /// identity for a BL label) and then `ObserverBasisBh`, so the gate
        /// fails if EITHER the chart sign or the basis sign is wrong, and
        /// fails independently of the kernel's momentum rotation.
        /// </summary>
        private string ObserverBasisProbeJson(float thetaDeg)
        {
            double theta = thetaDeg * Math.PI / 180.0;
            var parts = new System.Collections.Generic.List<string>();
            string Vec(double[] v) => $"[{v[0]:R},{v[1]:R},{v[2]:R}]";
            foreach (float overM in BasisProbeRadiiOverM)
            {
                double radius = overM * mass;
                double shift = PhiShiftSafe(radius);
                foreach (float azDeg in BasisProbeAzimuthsDeg)
                {
                    double azimuth = azDeg * Math.PI / 180.0;
                    for (int chart = 0; chart < 2; chart += 1)
                    {
                        bool ks = chart == 1;
                        double phiBl = ks ? azimuth - shift : azimuth;
                        ObserverBasisBh(theta, phiBl, out double[] right, out double[] up, out double[] forward);
                        parts.Add(
                            "{"
                            + $"\"rM\": {radius:R}, \"azimuthDeg\": {azDeg:R}, "
                            + $"\"chart\": \"{(ks ? "ks" : "bl")}\", \"thetaDeg\": {thetaDeg:R}, "
                            + $"\"rightBh\": {Vec(right)}, \"upBh\": {Vec(up)}, \"forwardBh\": {Vec(forward)}"
                            + "}"
                        );
                    }
                }
            }
            return "[" + string.Join(", ", parts) + "]";
        }

        private void Dump2D(RenderTexture source, string path)
        {
            var request = UnityEngine.Rendering.AsyncGPUReadback.Request(source, 0);
            request.WaitForCompletion();
            if (request.hasError)
            {
                throw new InvalidOperationException($"Readback failed for {path}.");
            }
            System.IO.File.WriteAllBytes(path, request.GetData<byte>(0).ToArray());
        }

        private void DumpArray(RenderTexture source, string path)
        {
            int width = source.width;
            int height = source.height;
            int sliceBytes = width * height * 16;
            var data = new byte[sliceBytes * 6];
            var request = UnityEngine.Rendering.AsyncGPUReadback.Request(source, 0);
            request.WaitForCompletion();
            if (request.hasError)
            {
                throw new InvalidOperationException($"Readback failed for {path}.");
            }
            for (int slice = 0; slice < 6; slice += 1)
            {
                byte[] managed = request.GetData<byte>(slice).ToArray();
                Buffer.BlockCopy(managed, 0, data, slice * sliceBytes, Math.Min(managed.Length, sliceBytes));
            }
            System.IO.File.WriteAllBytes(path, data);
        }

        private void ResolveReferences()
        {
            if (observerRig == null)
            {
                observerRig = FindAnyObjectByType<BlackHoleObserverRigControls>();
            }
            if (roamKeyframes == null)
            {
                roamKeyframes = FindAnyObjectByType<BlackHoleRoamKeyframes>();
            }
            if (targetMaterial == null)
            {
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
}
