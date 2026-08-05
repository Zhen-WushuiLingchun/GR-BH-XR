using System;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEditor.XR.Management;
using UnityEditor.XR.Management.Metadata;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.XR.Management;
using UnityEngine.XR.OpenXR;
using UnityEngine.XR.OpenXR.Features;
using UnityEngine.XR.OpenXR.Features.Interactions;

namespace GRBHXR.EditorTools
{
    public static class GRBHXRQuestPcvrSetup
    {
        private const string OpenXrLoaderTypeName = "UnityEngine.XR.OpenXR.OpenXRLoader";
        private const string DefaultScenePath = "Assets/Scenes/GRBHXR_KerrLensPreview.unity";
        private const string DefaultBuildPath = "../Builds/PCVR/GRBHXR_PCVR_Gate.exe";

        [MenuItem("GR-BH-XR/Quest PCVR/Configure OpenXR Loader")]
        public static void ConfigureOpenXrLoader()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isPlaying || EditorApplication.isPaused)
            {
                throw new InvalidOperationException("Exit Play mode before changing XR loader configuration.");
            }

            var buildTarget = BuildTargetGroup.Standalone;
            var settingsPerBuildTarget = GetOrCreateSettingsPerBuildTarget();

            if (!settingsPerBuildTarget.HasSettingsForBuildTarget(buildTarget))
            {
                settingsPerBuildTarget.CreateDefaultSettingsForBuildTarget(buildTarget);
            }

            if (!settingsPerBuildTarget.HasManagerSettingsForBuildTarget(buildTarget))
            {
                settingsPerBuildTarget.CreateDefaultManagerSettingsForBuildTarget(buildTarget);
            }

            var generalSettings = settingsPerBuildTarget.SettingsForBuildTarget(buildTarget);
            var managerSettings = settingsPerBuildTarget.ManagerSettingsForBuildTarget(buildTarget);
            if (generalSettings == null || managerSettings == null)
            {
                throw new InvalidOperationException("XR Management settings could not be created for Standalone.");
            }

            generalSettings.InitManagerOnStart = true;
            managerSettings.automaticLoading = true;
            managerSettings.automaticRunning = true;

            bool assigned = XRPackageMetadataStore.IsLoaderAssigned(OpenXrLoaderTypeName, buildTarget);
            if (!assigned && !XRPackageMetadataStore.AssignLoader(managerSettings, OpenXrLoaderTypeName, buildTarget))
            {
                throw new InvalidOperationException($"Failed to assign OpenXR loader: {OpenXrLoaderTypeName}");
            }
            string interactionFeatureSummary = EnableOpenXrControllerProfiles(buildTarget);

            EditorUtility.SetDirty(settingsPerBuildTarget);
            EditorUtility.SetDirty(generalSettings);
            EditorUtility.SetDirty(managerSettings);
            AssetDatabase.SaveAssets();

            string loaders = string.Join(", ", managerSettings.activeLoaders);
            Debug.Log(
                "GR-BH-XR Quest PCVR OpenXR loader configured: " +
                $"buildTarget={buildTarget}, initOnStart={generalSettings.InitManagerOnStart}, " +
                $"automaticLoading={managerSettings.automaticLoading}, automaticRunning={managerSettings.automaticRunning}, " +
                $"loaders=[{loaders}], interactionFeatures=[{interactionFeatureSummary}]"
            );
        }

        public static void BatchConfigureOpenXrLoader()
        {
            ConfigureOpenXrLoader();
        }

        [MenuItem("GR-BH-XR/Quest PCVR/Build Windows OpenXR Player")]
        public static void BuildWindowsOpenXrPlayer()
        {
            ConfigureOpenXrLoader();
            GRBHXRGateAutomation.ConfigurePcvrSkyShellFirstRun();

            string buildPath = CommandLineValue("-grbhxrBuildPath", DefaultBuildPath);
            string buildDirectory = Path.GetDirectoryName(buildPath);
            if (!string.IsNullOrWhiteSpace(buildDirectory))
            {
                Directory.CreateDirectory(buildDirectory);
            }

            PlayerSettings.companyName = "GRBHXR";
            PlayerSettings.productName = "GR-BH-XR PCVR Gate";
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.StandaloneWindows64, false);
            PlayerSettings.SetGraphicsAPIs(
                BuildTarget.StandaloneWindows64,
                new[] { UnityEngine.Rendering.GraphicsDeviceType.Direct3D11 }
            );

            var options = new BuildPlayerOptions
            {
                scenes = new[] { DefaultScenePath },
                locationPathName = buildPath,
                target = BuildTarget.StandaloneWindows64,
                targetGroup = BuildTargetGroup.Standalone,
                options = BuildOptions.None
            };

            BuildReport report = BuildPipeline.BuildPlayer(options);
            BuildSummary summary = report.summary;
            if (summary.result != BuildResult.Succeeded)
            {
                throw new InvalidOperationException(
                    $"GR-BH-XR PCVR player build failed: result={summary.result}, errors={summary.totalErrors}"
                );
            }

            Debug.Log(
                "GR-BH-XR PCVR player build succeeded: " +
                $"path={summary.outputPath}, size={summary.totalSize} bytes, warnings={summary.totalWarnings}"
            );
        }

        public static void BatchBuildWindowsOpenXrPlayer()
        {
            BuildWindowsOpenXrPlayer();
        }

        [MenuItem("GR-BH-XR/Quest PCVR/Open Scene And Enter Play Mode")]
        public static void OpenSceneAndEnterPlayMode()
        {
            ConfigureOpenXrLoader();

            if (!EditorSceneManager.GetActiveScene().path.EndsWith("GRBHXR_KerrLensPreview.unity", StringComparison.Ordinal))
            {
                EditorSceneManager.OpenScene(DefaultScenePath, OpenSceneMode.Single);
            }

            EditorApplication.delayCall += () =>
            {
                if (EditorApplication.isPlayingOrWillChangePlaymode)
                {
                    return;
                }

                Debug.Log("GR-BH-XR Quest PCVR entering Play mode with OpenXR loader.");
                EditorApplication.EnterPlaymode();
            };
        }

        private static XRGeneralSettingsPerBuildTarget GetOrCreateSettingsPerBuildTarget()
        {
            MethodInfo getOrCreate = typeof(XRGeneralSettingsPerBuildTarget).GetMethod(
                "GetOrCreate",
                BindingFlags.NonPublic | BindingFlags.Static
            );
            if (getOrCreate == null)
            {
                throw new MissingMethodException(nameof(XRGeneralSettingsPerBuildTarget), "GetOrCreate");
            }

            var settings = getOrCreate.Invoke(null, null) as XRGeneralSettingsPerBuildTarget;
            if (settings == null)
            {
                throw new InvalidOperationException("XRGeneralSettingsPerBuildTarget.GetOrCreate returned null.");
            }

            return settings;
        }

        private static string EnableOpenXrControllerProfiles(BuildTargetGroup buildTarget)
        {
            var settings = OpenXRSettings.GetSettingsForBuildTargetGroup(buildTarget);
            if (settings == null)
            {
                Debug.LogWarning(
                    $"GR-BH-XR could not find OpenXR package settings for {buildTarget}. " +
                    "Quest controller action maps will not be registered."
                );
                return "OpenXRSettings=null";
            }

            string metaQuestPlus = EnableFeature(settings.GetFeature<MetaQuestTouchPlusControllerProfile>(), "MetaQuestTouchPlus");
            string oculusTouch = EnableFeature(settings.GetFeature<OculusTouchControllerProfile>(), "OculusTouch");
            string simpleController = EnableFeature(settings.GetFeature<KHRSimpleControllerProfile>(), "KHRSimple");
            string environmentDepth = EnableFeature(settings.GetFeature<GRBHXREnvironmentDepthFeature>(), "GRBHXREnvironmentDepth");
            string metaXr = ReportMetaXrFeature(settings);
            EditorUtility.SetDirty(settings);
            return $"{metaQuestPlus}, {oculusTouch}, {simpleController}, {environmentDepth}, {metaXr}";
        }

        /// <summary>
        /// Report - deliberately without changing - the state of Meta's own
        /// OpenXR feature.
        ///
        /// Why this matters: MRUK initialises its native OpenXR layer only if
        /// OVRPlugin reports initialised, and under the Unity OpenXR loader
        /// OVRPlugin is initialised only by MetaXRFeature. If that feature is
        /// disabled, MRUK never calls InitOpenXr, PassthroughCameraAccess
        /// cannot start, and no repository-side change can work around it.
        ///
        /// Why this only reports: enabling MetaXRFeature adds roughly 95
        /// extensions to the OpenXR instance, which can perturb the
        /// environment-depth path that currently works. Requesting an
        /// unavailable extension can disable a working feature, so this is a
        /// deliberate configuration decision that needs a before/after
        /// capability probe, not a silent flip inside a setup helper.
        /// Resolved by reflection so the package keeps no compile-time
        /// dependency on Meta assemblies.
        /// </summary>
        private static string ReportMetaXrFeature(OpenXRSettings settings)
        {
            // Assembly is Oculus.VR - the Meta Core SDK's package-root asmdef.
            // Naming the UPM package here instead of the assembly would never
            // resolve, and the AppDomain fallback below would mask it in the
            // editor (where every assembly is already loaded) while failing in
            // a built player.
            var metaFeatureType = System.Type.GetType(
                "Meta.XR.MetaXRFeature, Oculus.VR", false
            );
            if (metaFeatureType == null)
            {
                foreach (var assembly in System.AppDomain.CurrentDomain.GetAssemblies())
                {
                    metaFeatureType = assembly.GetType("Meta.XR.MetaXRFeature", false);
                    if (metaFeatureType != null)
                    {
                        break;
                    }
                }
            }
            if (metaFeatureType == null)
            {
                Debug.Log(
                    "GR-BH-XR OpenXR: MetaXRFeature type not present (Meta Core SDK not installed). " +
                    "MRUK PassthroughCameraAccess cannot initialise without it."
                );
                return "MetaXRFeature=absent";
            }

            OpenXRFeature feature = null;
            foreach (OpenXRFeature candidate in settings.GetFeatures())
            {
                if (candidate != null && metaFeatureType.IsInstanceOfType(candidate))
                {
                    feature = candidate;
                    break;
                }
            }
            if (feature == null)
            {
                Debug.LogWarning("GR-BH-XR OpenXR: MetaXRFeature type exists but no feature instance was found.");
                return "MetaXRFeature=noInstance";
            }
            if (!feature.enabled)
            {
                Debug.LogWarning(
                    "GR-BH-XR OpenXR: MetaXRFeature is DISABLED for this build target. " +
                    "OVRPlugin will not initialise, so MRUK never calls InitOpenXr and " +
                    "PassthroughCameraAccess cannot deliver frames. This setup helper " +
                    "reports the state but does not change it: enabling MetaXRFeature adds " +
                    "~95 OpenXR extensions and can perturb the working environment-depth " +
                    "path, so it needs a deliberate decision plus a before/after capability " +
                    "probe. See docs and the MRUK source note."
                );
                return "MetaXRFeature=disabled(reported,notChanged)";
            }
            Debug.Log("GR-BH-XR OpenXR: MetaXRFeature is enabled.");
            return "MetaXRFeature=enabled";
        }

        private static string EnableFeature(OpenXRFeature feature, string label)
        {
            if (feature == null)
            {
                Debug.LogWarning($"GR-BH-XR OpenXR feature missing: {label}");
                return $"{label}=missing";
            }

            feature.enabled = true;
            EditorUtility.SetDirty(feature);
            return $"{label}=enabled:{feature.enabled}";
        }

        private static string CommandLineValue(string key, string fallback)
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i += 1)
            {
                if (string.Equals(args[i], key, StringComparison.OrdinalIgnoreCase))
                {
                    return args[i + 1];
                }
            }
            return fallback;
        }
    }
}
