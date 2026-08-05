using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.XR.OpenXR;
using UnityEngine.XR.OpenXR.Features;
using Debug = UnityEngine.Debug;

#if UNITY_EDITOR
using UnityEditor.XR.OpenXR.Features;
#endif

namespace GRBHXR
{
    /// <summary>
    /// Structured-light room depth over Link: a direct OpenXR binding of
    /// XR_META_environment_depth (probe-verified available on this runtime).
    /// The runtime reconstructs a per-eye depth map of the REAL room from the
    /// headset depth sensor; the MR path uses it to place lensed room samples
    /// at their true finite distance and to let real furniture occlude the
    /// hole. Every call is defensive: any failure logs and degrades to the
    /// calibrated room-sphere model, never crashes the session.
    /// </summary>
#if UNITY_EDITOR
    [OpenXRFeature(
        UiName = "GR-BH-XR Meta Environment Depth",
        Desc = "Binds XR_META_environment_depth for structured-light room depth over Link.",
        Company = "GRBHXR",
        OpenxrExtensionStrings = ExtensionNames,
        FeatureId = FeatureIdString,
        Version = "0.1.0")]
#endif
    public sealed class GRBHXREnvironmentDepthFeature : OpenXRFeature
    {
        public const string FeatureIdString = "com.grbhxr.meta.environmentdepth";
        public const string ExtensionNames =
            "XR_META_environment_depth XR_KHR_win32_convert_performance_counter_time XR_FB_passthrough";

        // XR_FB_passthrough is extension 119 -> enum base 1000118000.
        private const int TypePassthroughCreateInfo = 1000118001;
        private const ulong PassthroughIsRunningAtCreationBit = 0x1;
        // XR_META_environment_depth is extension 292 -> enum base 1000291000.
        private const int TypeProviderCreateInfo = 1000291000;
        private const int TypeSwapchainCreateInfo = 1000291001;
        private const int TypeSwapchainState = 1000291002;
        private const int TypeImageAcquireInfo = 1000291003;
        private const int TypeImageView = 1000291004;
        private const int TypeImage = 1000291005;
        private const int TypeSwapchainImageD3D11 = 1000027001;
        private const int ResultSuccess = 0;

        // ------------------------------------------------------------------
        // Struct marshaling (x64 layout mirrors the C headers).
        // ------------------------------------------------------------------
        [StructLayout(LayoutKind.Sequential)]
        private struct ProviderCreateInfo
        {
            public int type;
            public IntPtr next;
            public ulong createFlags;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct SwapchainCreateInfo
        {
            public int type;
            public IntPtr next;
            public ulong createFlags;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct SwapchainState
        {
            public int type;
            public IntPtr next;
            public uint width;
            public uint height;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct ImageAcquireInfo
        {
            public int type;
            public IntPtr next;
            public ulong space;
            public long displayTime;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct Fov
        {
            public float angleLeft;
            public float angleRight;
            public float angleUp;
            public float angleDown;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct Posef
        {
            public float qx;
            public float qy;
            public float qz;
            public float qw;
            public float px;
            public float py;
            public float pz;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct ImageView
        {
            public int type;
            public IntPtr next;
            public Fov fov;
            public Posef pose;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct ImageInfo
        {
            public int type;
            public IntPtr next;
            public uint swapchainIndex;
            public float nearZ;
            public float farZ;
            public ImageView view0;
            public ImageView view1;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct SwapchainImageD3D11
        {
            public int type;
            public IntPtr next;
            public IntPtr texture;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct PassthroughCreateInfo
        {
            public int type;
            public IntPtr next;
            public ulong flags;
        }

        // ------------------------------------------------------------------
        // Function delegates
        // ------------------------------------------------------------------
        private delegate int GetInstanceProcAddrDelegate(
            ulong instance, [MarshalAs(UnmanagedType.LPStr)] string name, out IntPtr function);

        private delegate int CreateProviderDelegate(
            ulong session, ref ProviderCreateInfo createInfo, out ulong provider);

        private delegate int ProviderOpDelegate(ulong provider);

        private delegate int CreateSwapchainDelegate(
            ulong provider, ref SwapchainCreateInfo createInfo, out ulong swapchain);

        private delegate int SwapchainStateDelegate(ulong swapchain, ref SwapchainState state);

        private delegate int EnumerateImagesDelegate(
            ulong swapchain, uint capacity, out uint count, IntPtr images);

        private delegate int AcquireImageDelegate(
            ulong provider, ref ImageAcquireInfo acquireInfo, ref ImageInfo image);

        private delegate int ConvertTimeDelegate(ulong instance, ref long counter, out long time);

        private delegate int CreatePassthroughDelegate(
            ulong session, ref PassthroughCreateInfo createInfo, out ulong passthrough);

        private delegate int PassthroughOpDelegate(ulong passthrough);

        private IntPtr rawGetInstanceProcAddr = IntPtr.Zero;
        private ulong xrInstance;
        private ulong xrSession;
        private ulong appSpace;
        private bool sessionBegun;
        private ulong provider;
        private ulong swapchain;
        private bool started;
        private bool initFailed;
        private uint width;
        private uint height;
        private Texture2D[] depthTextures = new Texture2D[0];
        private CreateProviderDelegate createProvider;
        private ProviderOpDelegate startProvider;
        private ProviderOpDelegate destroyProvider;
        private CreateSwapchainDelegate createSwapchain;
        private SwapchainStateDelegate getSwapchainState;
        private EnumerateImagesDelegate enumerateImages;
        private AcquireImageDelegate acquireImage;
        private ConvertTimeDelegate convertTime;

        private ulong passthroughHandle;
        private bool passthroughTried;

        public bool DepthAvailable => started && depthTextures.Length > 0;
        public uint Width => width;
        public uint Height => height;
        public string LastStatus { get; private set; } = "not initialized";
        public string PassthroughStatus { get; private set; } = "not started";

        /// <summary>Create and run an XrPassthroughFB session. Two purposes:
        /// the Link camera pipeline may require an active passthrough session
        /// before the virtual camera device delivers frames, and this handle
        /// is step one toward a runtime-composited passthrough underlay.</summary>
        public bool EnsurePassthroughStarted()
        {
            if (passthroughHandle != 0)
            {
                return true;
            }
            if (passthroughTried || !sessionBegun || xrInstance == 0 || xrSession == 0
                || rawGetInstanceProcAddr == IntPtr.Zero)
            {
                return false;
            }
            passthroughTried = true;
            if (!OpenXRRuntime.IsExtensionEnabled("XR_FB_passthrough"))
            {
                PassthroughStatus = "XR_FB_passthrough not enabled";
                Debug.LogWarning($"GR-BH-XR passthrough: {PassthroughStatus}");
                return false;
            }
            try
            {
                var getProc = Marshal.GetDelegateForFunctionPointer<GetInstanceProcAddrDelegate>(
                    rawGetInstanceProcAddr);
                if (!Resolve(getProc, "xrCreatePassthroughFB", out CreatePassthroughDelegate create)
                    || !Resolve(getProc, "xrPassthroughStartFB", out PassthroughOpDelegate start))
                {
                    PassthroughStatus = "function resolution failed";
                    return false;
                }
                var createInfo = new PassthroughCreateInfo
                {
                    type = TypePassthroughCreateInfo,
                    flags = PassthroughIsRunningAtCreationBit,
                };
                int result = create(xrSession, ref createInfo, out passthroughHandle);
                if (result != ResultSuccess)
                {
                    PassthroughStatus = $"xrCreatePassthroughFB -> {result}";
                    Debug.LogWarning($"GR-BH-XR passthrough: {PassthroughStatus}");
                    passthroughHandle = 0;
                    return false;
                }
                start(passthroughHandle);
                PassthroughStatus = "running";
                Debug.Log("GR-BH-XR passthrough: XrPassthroughFB created and running.");
                return true;
            }
            catch (Exception exception)
            {
                PassthroughStatus = $"exception: {exception.Message}";
                Debug.LogWarning($"GR-BH-XR passthrough: {PassthroughStatus}");
                return false;
            }
        }

        public static GRBHXREnvironmentDepthFeature Instance
        {
            get
            {
                var settings = OpenXRSettings.Instance;
                return settings != null ? settings.GetFeature<GRBHXREnvironmentDepthFeature>() : null;
            }
        }

        protected override IntPtr HookGetInstanceProcAddr(IntPtr func)
        {
            rawGetInstanceProcAddr = func;
            return func;
        }

        protected override bool OnInstanceCreate(ulong instance)
        {
            xrInstance = instance;
            return true;
        }

        protected override void OnSessionCreate(ulong session)
        {
            xrSession = session;
        }

        protected override void OnSessionBegin(ulong session)
        {
            sessionBegun = true;
        }

        protected override void OnAppSpaceChange(ulong space)
        {
            appSpace = space;
        }

        protected override void OnSessionDestroy(ulong session)
        {
            Shutdown();
            xrSession = 0;
            sessionBegun = false;
        }

        /// <summary>Lazy provider bring-up; safe to call every frame.</summary>
        public bool EnsureStarted()
        {
            if (started)
            {
                return true;
            }
            if (initFailed || !sessionBegun || xrInstance == 0 || xrSession == 0
                || rawGetInstanceProcAddr == IntPtr.Zero)
            {
                return false;
            }
            if (!OpenXRRuntime.IsExtensionEnabled("XR_META_environment_depth"))
            {
                LastStatus = "extension not enabled by runtime";
                initFailed = true;
                return false;
            }
            try
            {
                return Initialize();
            }
            catch (Exception exception)
            {
                LastStatus = $"init exception: {exception.Message}";
                Debug.LogWarning($"GR-BH-XR depth: {LastStatus}");
                initFailed = true;
                return false;
            }
        }

        private bool Initialize()
        {
            var getProc = Marshal.GetDelegateForFunctionPointer<GetInstanceProcAddrDelegate>(
                rawGetInstanceProcAddr);
            if (!Resolve(getProc, "xrCreateEnvironmentDepthProviderMETA", out createProvider)
                || !Resolve(getProc, "xrStartEnvironmentDepthProviderMETA", out startProvider)
                || !Resolve(getProc, "xrDestroyEnvironmentDepthProviderMETA", out destroyProvider)
                || !Resolve(getProc, "xrCreateEnvironmentDepthSwapchainMETA", out createSwapchain)
                || !Resolve(getProc, "xrGetEnvironmentDepthSwapchainStateMETA", out getSwapchainState)
                || !Resolve(getProc, "xrEnumerateEnvironmentDepthSwapchainImagesMETA", out enumerateImages)
                || !Resolve(getProc, "xrAcquireEnvironmentDepthImageMETA", out acquireImage)
                || !Resolve(getProc, "xrConvertWin32PerformanceCounterToTimeKHR", out convertTime))
            {
                LastStatus = "function resolution failed";
                initFailed = true;
                return false;
            }

            var providerInfo = new ProviderCreateInfo { type = TypeProviderCreateInfo };
            int result = createProvider(xrSession, ref providerInfo, out provider);
            if (result != ResultSuccess)
            {
                LastStatus = $"xrCreateEnvironmentDepthProviderMETA -> {result}";
                Debug.LogWarning($"GR-BH-XR depth: {LastStatus}");
                initFailed = true;
                return false;
            }

            var swapchainInfo = new SwapchainCreateInfo { type = TypeSwapchainCreateInfo };
            result = createSwapchain(provider, ref swapchainInfo, out swapchain);
            if (result != ResultSuccess)
            {
                LastStatus = $"xrCreateEnvironmentDepthSwapchainMETA -> {result}";
                Debug.LogWarning($"GR-BH-XR depth: {LastStatus}");
                initFailed = true;
                return false;
            }

            var state = new SwapchainState { type = TypeSwapchainState };
            result = getSwapchainState(swapchain, ref state);
            if (result != ResultSuccess)
            {
                LastStatus = $"xrGetEnvironmentDepthSwapchainStateMETA -> {result}";
                Debug.LogWarning($"GR-BH-XR depth: {LastStatus}");
                initFailed = true;
                return false;
            }
            width = state.width;
            height = state.height;

            result = enumerateImages(swapchain, 0, out uint count, IntPtr.Zero);
            if (result != ResultSuccess || count == 0)
            {
                LastStatus = $"image count enumerate -> {result}, count={count}";
                Debug.LogWarning($"GR-BH-XR depth: {LastStatus}");
                initFailed = true;
                return false;
            }
            int stride = Marshal.SizeOf<SwapchainImageD3D11>();
            IntPtr buffer = Marshal.AllocHGlobal(stride * (int)count);
            try
            {
                for (int i = 0; i < count; i += 1)
                {
                    var image = new SwapchainImageD3D11 { type = TypeSwapchainImageD3D11 };
                    Marshal.StructureToPtr(image, buffer + i * stride, false);
                }
                result = enumerateImages(swapchain, count, out count, buffer);
                if (result != ResultSuccess)
                {
                    LastStatus = $"image enumerate -> {result}";
                    Debug.LogWarning($"GR-BH-XR depth: {LastStatus}");
                    initFailed = true;
                    return false;
                }
                depthTextures = new Texture2D[count];
                for (int i = 0; i < count; i += 1)
                {
                    var image = Marshal.PtrToStructure<SwapchainImageD3D11>(buffer + i * stride);
                    // The swapchain images are 2-slice arrays (one per eye);
                    // the wrapper binds slice 0 (left). Wrapping can fail on
                    // some formats - contained, logged, degrades to sphere.
                    depthTextures[i] = Texture2D.CreateExternalTexture(
                        (int)width, (int)height, TextureFormat.R16,
                        mipChain: false, linear: true, nativeTex: image.texture);
                }
            }
            finally
            {
                Marshal.FreeHGlobal(buffer);
            }

            result = startProvider(provider);
            if (result != ResultSuccess)
            {
                LastStatus = $"xrStartEnvironmentDepthProviderMETA -> {result}";
                Debug.LogWarning($"GR-BH-XR depth: {LastStatus}");
                initFailed = true;
                return false;
            }
            started = true;
            LastStatus = $"started: {width}x{height}, {depthTextures.Length} swapchain images";
            Debug.Log($"GR-BH-XR depth: {LastStatus}");
            return true;
        }

        private bool Resolve<T>(GetInstanceProcAddrDelegate getProc, string name, out T target)
            where T : Delegate
        {
            target = null;
            int result = getProc(xrInstance, name, out IntPtr pointer);
            if (result != ResultSuccess || pointer == IntPtr.Zero)
            {
                Debug.LogWarning($"GR-BH-XR depth: cannot resolve {name} ({result}).");
                return false;
            }
            target = Marshal.GetDelegateForFunctionPointer<T>(pointer);
            return true;
        }

        /// <summary>Acquire the latest depth image metadata + texture. Returns
        /// false (with status) when depth is momentarily unavailable.</summary>
        public bool TryAcquire(out Texture2D texture, out ImageView leftView, out float nearZ, out float farZ)
        {
            texture = null;
            leftView = default;
            nearZ = 0.0f;
            farZ = 0.0f;
            if (!EnsureStarted())
            {
                return false;
            }
            long counter = Stopwatch.GetTimestamp();
            int result = convertTime(xrInstance, ref counter, out long xrTime);
            if (result != ResultSuccess)
            {
                LastStatus = $"time convert -> {result}";
                return false;
            }
            var acquireInfo = new ImageAcquireInfo
            {
                type = TypeImageAcquireInfo,
                space = appSpace,
                displayTime = xrTime,
            };
            var image = new ImageInfo
            {
                type = TypeImage,
                view0 = new ImageView { type = TypeImageView },
                view1 = new ImageView { type = TypeImageView },
            };
            result = acquireImage(provider, ref acquireInfo, ref image);
            if (result != ResultSuccess)
            {
                LastStatus = $"acquire -> {result}";
                return false;
            }
            if (image.swapchainIndex >= depthTextures.Length || depthTextures[image.swapchainIndex] == null)
            {
                LastStatus = $"acquire index {image.swapchainIndex} out of range";
                return false;
            }
            texture = depthTextures[image.swapchainIndex];
            leftView = image.view0;
            nearZ = image.nearZ;
            farZ = image.farZ;
            LastStatus = $"ok idx={image.swapchainIndex} near={image.nearZ:F3} far={image.farZ:F1}";
            return true;
        }

        private void Shutdown()
        {
            if (provider != 0 && destroyProvider != null)
            {
                destroyProvider(provider);
            }
            provider = 0;
            swapchain = 0;
            started = false;
            depthTextures = new Texture2D[0];
            passthroughHandle = 0;
            passthroughTried = false;
        }
    }
}
