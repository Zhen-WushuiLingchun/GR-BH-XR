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
            // Fail closed before anything mutates the project. ConfigureOpenXrLoader
            // saves XR settings assets, ConfigurePcvrSkyShellFirstRun overwrites the
            // saved scene, and the PlayerSettings writes below are persistent, so a
            // render pipeline asset check placed any later would leave the project
            // modified by a build that cannot succeed. This never repairs; repair is
            // an explicit, separate operator action.
            GRBHXRUrpAssetRepair.AssertProjectUrpAssetsCompatible();

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
            EditorUtility.SetDirty(settings);
            return $"{metaQuestPlus}, {oculusTouch}, {simpleController}";
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
