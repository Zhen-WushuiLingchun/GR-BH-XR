using System;
using System.IO;
using GRBHXR;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace GRBHXR.EditorTools
{
    public static class GRBHXRGateAutomation
    {
        private const string DefaultLensMapDir = "Assets/GRBHXR/LensMaps/Kerr_a09_i60_1024_to_4k_display";
        private const string DefaultCubemapPath = "Assets/GRBHXR/Skyboxes/NASA_DeepStarMap2020.cubemap";
        private const string DefaultSkyboxMaterialPath = "Assets/GRBHXR/Skyboxes/M_NASA_DeepStarMap2020_Skybox.mat";
        private const string DefaultQuadrantCubemapPath = "Assets/GRBHXR/Skyboxes/GRBHXR_QuadrantHandedness.cubemap";
        private const string DefaultQuadrantSkyboxMaterialPath = "Assets/GRBHXR/Skyboxes/M_GRBHXR_QuadrantHandedness_Skybox.mat";
        private const string DefaultProtractorCubemapPath = "Assets/GRBHXR/Skyboxes/GRBHXR_ProtractorBands.cubemap";
        private const string DefaultProtractorSkyboxMaterialPath = "Assets/GRBHXR/Skyboxes/M_GRBHXR_ProtractorBands_Skybox.mat";
        private const string DefaultMaterialPath = "Assets/GRBHXR/Materials/M_KerrLensPreview.mat";
        private const string DefaultScenePath = "Assets/Scenes/GRBHXR_KerrLensPreview.unity";
        private const string DefaultFullSkyTransferDir = "Assets/GRBHXR/FullSkyTransfer1024";
        private const string DefaultCaptureDir = "F:/学习和研究/GR-BH-XR/outputs/task5/unity_gate";

        [MenuItem("GR-BH-XR/Gate/Configure Screen-Space Gate Preview")]
        public static void ConfigureScreenSpaceGatePreview()
        {
            var options = GateOptions.FromCommandLine();
            ConfigurePreview(options, GateSkyboxKind.Nasa);
        }

        [MenuItem("GR-BH-XR/Gate/Configure And Capture")]
        public static void ConfigureAndCapture()
        {
            var options = GateOptions.FromCommandLine();
            ConfigurePreview(options, GateSkyboxKind.Nasa);
            Capture(options, "unity_gate_square_2048.png", 2048, 2048);
            Capture(options, "unity_gate_wide_1920x1080.png", 1920, 1080);
            AssetDatabase.Refresh();
        }

        [MenuItem("GR-BH-XR/Gate/Capture Quadrant Handedness")]
        public static void CaptureQuadrantHandedness()
        {
            var options = GateOptions.FromCommandLine();
            ConfigurePreview(options, GateSkyboxKind.Quadrant);
            Capture(options, "unity_gate_quadrant_square_1024.png", 1024, 1024);
            Capture(options, "unity_gate_quadrant_wide_1920x1080.png", 1920, 1080);
            AssetDatabase.Refresh();
        }

        [MenuItem("GR-BH-XR/Gate/Capture Protractor Bands")]
        public static void CaptureProtractorBands()
        {
            var options = GateOptions.FromCommandLine();
            ConfigurePreview(options, GateSkyboxKind.Protractor);
            Capture(options, "unity_gate_protractor_square_1024.png", 1024, 1024);
            Capture(options, "unity_gate_protractor_wide_1920x1080.png", 1920, 1080);
            AssetDatabase.Refresh();
        }

        [MenuItem("GR-BH-XR/Gate/Capture Angular Window Yaw Gate")]
        public static void CaptureAngularWindowYawGate()
        {
            var options = GateOptions.FromCommandLine();
            options.UseAngularWindow = true;
            ConfigurePreview(options, GateSkyboxKind.Nasa);
            CaptureYaw(options, 0.0f, "unity_gate_angular_yaw_000_square_1024.png", 1024, 1024);
            CaptureYaw(options, 2.0f, "unity_gate_angular_yaw_002_square_1024.png", 1024, 1024);
            CaptureYaw(options, 4.0f, "unity_gate_angular_yaw_004_square_1024.png", 1024, 1024);
            AssetDatabase.Refresh();
        }

        [MenuItem("GR-BH-XR/Gate/Capture Full-Sky Protractor Yaw Gate")]
        public static void CaptureFullSkyProtractorYawGate()
        {
            var options = GateOptions.FromCommandLine();
            options.UseAngularWindow = true;
            ConfigurePreview(options, GateSkyboxKind.Protractor);
            CaptureYaw(options, 0.0f, "unity_gate_fullsky_protractor_yaw_000_square_1024.png", 1024, 1024);
            CaptureYaw(options, 2.0f, "unity_gate_fullsky_protractor_yaw_002_square_1024.png", 1024, 1024);
            CaptureYaw(options, 4.0f, "unity_gate_fullsky_protractor_yaw_004_square_1024.png", 1024, 1024);
            AssetDatabase.Refresh();
        }

        [MenuItem("GR-BH-XR/Gate/Capture Full-Sky Disk Audit Gate")]
        public static void CaptureFullSkyDiskAuditGate()
        {
            var options = GateOptions.FromCommandLine();
            options.UseAngularWindow = true;
            options.DiskAuditMode = 1.0f;
            ConfigurePreview(options, GateSkyboxKind.Nasa);
            CaptureYaw(options, 0.0f, "unity_gate_fullsky_disk_audit_m0_square_1024.png", 1024, 1024);
            var material = AssetDatabase.LoadAssetAtPath<Material>(options.MaterialPath);
            if (material == null)
            {
                throw new MissingReferenceException($"Material not found: {options.MaterialPath}");
            }
            material.SetFloat("_DiskAuditMode", 2.0f);
            EditorUtility.SetDirty(material);
            CaptureYaw(options, 0.0f, "unity_gate_fullsky_disk_audit_m1_square_1024.png", 1024, 1024);
            AssetDatabase.Refresh();
        }

        [MenuItem("GR-BH-XR/Gate/Configure PCVR Sky-Shell First Run")]
        public static void ConfigurePcvrSkyShellFirstRun()
        {
            var options = GateOptions.FromCommandLine();
            options.UseAngularWindow = true;
            options.UseSkyShell = true;
            ConfigurePreview(options, GateSkyboxKind.Nasa);
            AssetDatabase.Refresh();
        }

        public static void BatchConfigureAndCapture()
        {
            ConfigureAndCapture();
        }

        public static void BatchCaptureQuadrantHandedness()
        {
            CaptureQuadrantHandedness();
        }

        public static void BatchCaptureProtractorBands()
        {
            CaptureProtractorBands();
        }

        public static void BatchCaptureAngularWindowYawGate()
        {
            CaptureAngularWindowYawGate();
        }

        public static void BatchCaptureFullSkyProtractorYawGate()
        {
            CaptureFullSkyProtractorYawGate();
        }

        public static void BatchCaptureFullSkyDiskAuditGate()
        {
            CaptureFullSkyDiskAuditGate();
        }

        public static void BatchConfigurePcvrSkyShellFirstRun()
        {
            ConfigurePcvrSkyShellFirstRun();
        }

        private static void ConfigurePreview(GateOptions options, GateSkyboxKind skyboxKind)
        {
            AssetDatabase.Refresh();

            var metadataAsset = LoadRequired<TextAsset>($"{options.LensMapDir}/lens_map_metadata.json");
            var eventBytes = LoadRequired<TextAsset>($"{options.LensMapDir}/event_rgba8.bytes");
            var escapeBytes = LoadRequired<TextAsset>($"{options.LensMapDir}/escape_dir_unity_rgba32f.bytes");
            TextAsset fullSkyMetadata = null;
            TextAsset eventCubeBytes = null;
            TextAsset escapeCubeBytes = null;
            TextAsset diskOrder0CubeBytes = null;
            TextAsset diskOrder1CubeBytes = null;
            TextAsset diskColorLutMetadata = null;
            TextAsset diskColorLutBytes = null;
            TextAsset diskRadialLutMetadata = null;
            TextAsset diskRadialLutBytes = null;
            bool useFullSkyTransfer = !string.IsNullOrWhiteSpace(options.FullSkyTransferDir);
            if (useFullSkyTransfer)
            {
                fullSkyMetadata = LoadRequired<TextAsset>($"{options.FullSkyTransferDir}/full_sky_transfer_metadata.json");
                eventCubeBytes = LoadRequired<TextAsset>($"{options.FullSkyTransferDir}/event_cube_rgba8.bytes");
                escapeCubeBytes = LoadRequired<TextAsset>($"{options.FullSkyTransferDir}/escape_dir_unity_cube_rgba32f.bytes");
                diskOrder0CubeBytes = AssetDatabase.LoadAssetAtPath<TextAsset>(
                    $"{options.FullSkyTransferDir}/disk_order0_transfer_cube_rgba16f.bytes"
                );
                diskOrder1CubeBytes = AssetDatabase.LoadAssetAtPath<TextAsset>(
                    $"{options.FullSkyTransferDir}/disk_order1_transfer_cube_rgba16f.bytes"
                );
                diskColorLutMetadata = AssetDatabase.LoadAssetAtPath<TextAsset>(
                    $"{options.FullSkyTransferDir}/disk_color_lut_metadata.json"
                );
                diskColorLutBytes = AssetDatabase.LoadAssetAtPath<TextAsset>(
                    $"{options.FullSkyTransferDir}/disk_color_lut_rgba32f.bytes"
                );
                diskRadialLutMetadata = AssetDatabase.LoadAssetAtPath<TextAsset>(
                    $"{options.FullSkyTransferDir}/disk_radial_lut_metadata.json"
                );
                diskRadialLutBytes = AssetDatabase.LoadAssetAtPath<TextAsset>(
                    $"{options.FullSkyTransferDir}/disk_radial_lut_rgba32f.bytes"
                );
            }
            var metadata = JsonUtility.FromJson<LensMapMetadata>(metadataAsset.text);
            if (metadata == null || metadata.screen == null)
            {
                throw new InvalidOperationException("Lens-map metadata is missing screen bounds.");
            }

            var shader = Shader.Find("GR-BH-XR/Kerr Lens Static Preview");
            if (shader == null)
            {
                throw new MissingReferenceException("Shader not found: GR-BH-XR/Kerr Lens Static Preview");
            }

            Cubemap cubemap;
            Material skyboxMaterial;
            if (skyboxKind == GateSkyboxKind.Quadrant)
            {
                cubemap = EnsureQuadrantCubemap(options.QuadrantCubemapPath);
                skyboxMaterial = EnsureSkyboxMaterial(options.QuadrantSkyboxMaterialPath, cubemap);
            }
            else if (skyboxKind == GateSkyboxKind.Protractor)
            {
                cubemap = EnsureProtractorCubemap(options.ProtractorCubemapPath);
                skyboxMaterial = EnsureSkyboxMaterial(options.ProtractorSkyboxMaterialPath, cubemap);
            }
            else
            {
                cubemap = LoadRequired<Cubemap>(options.CubemapPath);
                skyboxMaterial = AssetDatabase.LoadAssetAtPath<Material>(options.SkyboxMaterialPath);
            }

            var material = AssetDatabase.LoadAssetAtPath<Material>(options.MaterialPath);
            if (material == null)
            {
                EnsureFolder("Assets/GRBHXR");
                EnsureFolder("Assets/GRBHXR/Materials");
                material = new Material(shader) { name = Path.GetFileNameWithoutExtension(options.MaterialPath) };
                AssetDatabase.CreateAsset(material, options.MaterialPath);
            }
            material.shader = shader;
            material.SetTexture("_SkyboxCubemap", cubemap);
            material.SetFloat("_UseAngularWindow", options.UseAngularWindow ? 1.0f : 0.0f);
            material.SetFloat("_UseFullSkyTransfer", useFullSkyTransfer ? 1.0f : 0.0f);
            material.SetFloat("_DiskVisualMode", options.DiskVisualMode ? 1.0f : 0.0f);
            material.SetFloat("_DiskAuditMode", options.DiskAuditMode);
            material.SetFloat("_DiskOpacity", 0.85f);
            material.SetFloat("_DiskBrightness", 1.0f);
            material.SetFloat("_DiskGPower", 3.0f);
            material.SetFloat("_DiskSecondaryScale", 0.32f);
            material.SetFloat(
                "_UseDiskColorLut",
                diskColorLutBytes != null && diskRadialLutBytes != null ? 1.0f : 0.0f
            );
            material.SetFloat("_ProbeMode", skyboxKind == GateSkyboxKind.Protractor ? 1.0f : 0.0f);
            material.SetFloat("_SkyboxLodBias", 0.0f);
            material.SetFloat("_StrongLensLodBias", 0.85f);
            EditorUtility.SetDirty(material);

            var screen = GameObject.Find("LensScreen");
            var skyShell = GameObject.Find("LensSkyShell");
            GameObject previewObject;
            if (options.UseSkyShell)
            {
                if (skyShell == null)
                {
                    skyShell = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                    skyShell.name = "LensSkyShell";
                }
                if (screen != null)
                {
                    screen.SetActive(false);
                }
                skyShell.SetActive(true);
                previewObject = skyShell;
                previewObject.transform.position = Vector3.zero;
                previewObject.transform.rotation = Quaternion.identity;
                previewObject.transform.localScale = new Vector3(200.0f, 200.0f, 200.0f);
            }
            else
            {
                if (screen == null)
                {
                    screen = GameObject.CreatePrimitive(PrimitiveType.Quad);
                    screen.name = "LensScreen";
                }
                if (skyShell != null)
                {
                    skyShell.SetActive(false);
                }
                screen.SetActive(true);
                previewObject = screen;
                previewObject.transform.position = Vector3.zero;
                previewObject.transform.rotation = Quaternion.identity;
                previewObject.transform.localScale = new Vector3(20.0f, 20.0f, 20.0f);
            }
            previewObject.GetComponent<MeshRenderer>().sharedMaterial = material;

            var lensMap = previewObject.GetComponent<BlackHoleLensMap>();
            if (lensMap == null)
            {
                lensMap = previewObject.AddComponent<BlackHoleLensMap>();
            }
            AssignSerializedObject(lensMap, "metadataJson", metadataAsset);
            AssignSerializedObject(lensMap, "eventRgba8Bytes", eventBytes);
            AssignSerializedObject(lensMap, "escapeDirectionUnityRgba32fBytes", escapeBytes);
            AssignSerializedObject(lensMap, "fullSkyMetadataJson", fullSkyMetadata);
            AssignSerializedObject(lensMap, "eventCubeRgba8Bytes", eventCubeBytes);
            AssignSerializedObject(lensMap, "escapeDirectionUnityCubeRgba32fBytes", escapeCubeBytes);
            AssignSerializedObject(lensMap, "diskOrder0TransferCubeRgba16fBytes", diskOrder0CubeBytes);
            AssignSerializedObject(lensMap, "diskOrder1TransferCubeRgba16fBytes", diskOrder1CubeBytes);
            AssignSerializedObject(lensMap, "diskColorLutMetadataJson", diskColorLutMetadata);
            AssignSerializedObject(lensMap, "diskColorLutRgba32fBytes", diskColorLutBytes);
            AssignSerializedObject(lensMap, "diskRadialLutMetadataJson", diskRadialLutMetadata);
            AssignSerializedObject(lensMap, "diskRadialLutRgba32fBytes", diskRadialLutBytes);

            var binder = previewObject.GetComponent<BlackHoleLensMaterialBinder>();
            if (binder == null)
            {
                binder = previewObject.AddComponent<BlackHoleLensMaterialBinder>();
            }
            AssignSerializedObject(binder, "targetMaterial", material);

            var runtimeSettings = previewObject.GetComponent<BlackHoleLensRuntimeSettings>();
            if (runtimeSettings == null)
            {
                runtimeSettings = previewObject.AddComponent<BlackHoleLensRuntimeSettings>();
            }
            AssignSerializedObject(runtimeSettings, "targetMaterial", material);
            AssignSerializedObject(runtimeSettings, "targetRenderer", previewObject.GetComponent<Renderer>());
            AssignSerializedBool(runtimeSettings, "diskVisualMode", options.DiskVisualMode);
            AssignSerializedInt(runtimeSettings, "diskAuditMode", Mathf.RoundToInt(options.DiskAuditMode));
            AssignSerializedFloat(runtimeSettings, "diskOpacity", 0.85f);
            AssignSerializedFloat(runtimeSettings, "diskBrightness", 1.0f);
            AssignSerializedFloat(runtimeSettings, "diskGPower", 3.0f);
            AssignSerializedFloat(runtimeSettings, "diskSecondaryScale", 0.32f);
            lensMap.Load();
            lensMap.ApplyToMaterial(material);
            runtimeSettings.Apply();

            var camera = Camera.main;
            if (camera == null)
            {
                var cameraObject = new GameObject("Main Camera");
                camera = cameraObject.AddComponent<Camera>();
                cameraObject.tag = "MainCamera";
            }
            camera.transform.position = new Vector3(0.0f, 0.0f, -3.0f);
            camera.transform.rotation = Quaternion.identity;
            camera.orthographic = false;
            camera.clearFlags = CameraClearFlags.Skybox;
            camera.backgroundColor = Color.black;
            camera.nearClipPlane = 0.01f;
            camera.farClipPlane = 1000.0f;
            var headPoseDriver = camera.GetComponent<BlackHoleXrHeadPoseDriver>();
            if (headPoseDriver == null)
            {
                headPoseDriver = camera.gameObject.AddComponent<BlackHoleXrHeadPoseDriver>();
            }

            var lensAnchor = GameObject.Find("BlackHoleLensAnchor");
            if (lensAnchor == null)
            {
                lensAnchor = new GameObject("BlackHoleLensAnchor");
            }
            lensAnchor.transform.position = Vector3.zero;
            lensAnchor.transform.rotation = Quaternion.identity;
            lensAnchor.transform.localScale = Vector3.one;

            if (options.UseSkyShell)
            {
                var skyShellComponent = previewObject.GetComponent<BlackHoleXrSkyShell>();
                if (skyShellComponent == null)
                {
                    skyShellComponent = previewObject.AddComponent<BlackHoleXrSkyShell>();
                }
                AssignSerializedObject(skyShellComponent, "targetCamera", camera);
                AssignSerializedObject(skyShellComponent, "lensAnchor", lensAnchor.transform);
                AssignSerializedObject(skyShellComponent, "lensMap", lensMap);
                AssignSerializedObject(skyShellComponent, "targetMaterial", material);
                AssignSerializedFloat(skyShellComponent, "shellDiameter", 200.0f);
                AssignSerializedBool(skyShellComponent, "followCameraPosition", true);
                AssignSerializedBool(skyShellComponent, "refreshBasisEveryFrame", true);
                skyShellComponent.SyncNow();

                var controls = lensAnchor.GetComponent<BlackHoleLensAnchorControls>();
                if (controls == null)
                {
                    controls = lensAnchor.AddComponent<BlackHoleLensAnchorControls>();
                }
                AssignSerializedObject(controls, "lensAnchor", lensAnchor.transform);
                AssignSerializedObject(controls, "skyShell", skyShellComponent);
                AssignSerializedBool(controls, "enableMouseKeyboardInput", true);
                controls.ResetPose();

                var xrControls = lensAnchor.GetComponent<BlackHoleLensXrControllerControls>();
                if (xrControls == null)
                {
                    xrControls = lensAnchor.AddComponent<BlackHoleLensXrControllerControls>();
                }
                AssignSerializedObject(xrControls, "controls", controls);
                AssignSerializedObject(xrControls, "runtimeSettings", runtimeSettings);

                var settingsPanelObject = GameObject.Find("LensSettingsPanel");
                if (settingsPanelObject == null)
                {
                    settingsPanelObject = new GameObject("LensSettingsPanel");
                }
                var settingsPanel = settingsPanelObject.GetComponent<BlackHoleLensSettingsPanel>();
                if (settingsPanel == null)
                {
                    settingsPanel = settingsPanelObject.AddComponent<BlackHoleLensSettingsPanel>();
                }
                AssignSerializedObject(settingsPanel, "targetCamera", camera);
                AssignSerializedObject(settingsPanel, "controls", controls);
                AssignSerializedObject(settingsPanel, "runtimeSettings", runtimeSettings);
                AssignSerializedBool(settingsPanel, "visible", options.ShowControlPanel);
                settingsPanel.SetVisible(options.ShowControlPanel, placeInFrontOfCamera: true);
                AssignSerializedObject(xrControls, "settingsPanel", settingsPanel);

                var panelObject = GameObject.Find("LensControlPanel");
                if (panelObject == null)
                {
                    panelObject = new GameObject("LensControlPanel");
                }
                var panel = panelObject.GetComponent<BlackHoleLensFloatingPanel>();
                if (panel == null)
                {
                    panel = panelObject.AddComponent<BlackHoleLensFloatingPanel>();
                }
                AssignSerializedObject(panel, "targetCamera", camera);
                AssignSerializedObject(panel, "controls", controls);
                AssignSerializedObject(panel, "headPoseDriver", headPoseDriver);
                AssignSerializedObject(panel, "xrControllerControls", xrControls);
                AssignSerializedObject(panel, "runtimeSettings", runtimeSettings);
                AssignSerializedBool(panel, "followCamera", true);
                AssignSerializedBool(panel, "visible", false);
                AssignSerializedFloat(panel, "textCharacterSize", 0.013f);
                AssignSerializedVector3(panel, "cameraLocalOffset", new Vector3(0.0f, 0.28f, 1.55f));
                panel.RefreshNow();
                AssignSerializedObject(xrControls, "floatingPanel", panel);
            }

            float rObs = metadata.sourceAttributes != null && metadata.sourceAttributes.r_obs > 0.0f
                ? metadata.sourceAttributes.r_obs
                : 100.0f;
            float betaHalfWidth = Mathf.Max(Mathf.Abs(metadata.screen.betaMin), Mathf.Abs(metadata.screen.betaMax));
            camera.fieldOfView = 2.0f * Mathf.Atan(betaHalfWidth / rObs) * Mathf.Rad2Deg;

            if (skyboxMaterial != null)
            {
                RenderSettings.skybox = skyboxMaterial;
            }

            EnsureFolder(Path.GetDirectoryName(options.ScenePath)?.Replace('\\', '/') ?? "Assets/Scenes");
            EditorSceneManager.SaveScene(SceneManager.GetActiveScene(), options.ScenePath);
            Debug.Log(
                $"GR-BH-XR gate configured: fov={camera.fieldOfView:F4} deg, " +
                $"r_obs={rObs:F3}, beta=[{metadata.screen.betaMin:F3},{metadata.screen.betaMax:F3}], " +
                $"skyboxKind={skyboxKind}, angularWindow={options.UseAngularWindow}, " +
                $"skyShell={options.UseSkyShell}, " +
                $"fullSkyTransfer={useFullSkyTransfer}, fullSkyDir={options.FullSkyTransferDir}, " +
                $"lossyScale={previewObject.transform.lossyScale}, probeMode={material.GetFloat("_ProbeMode"):F1}, " +
                $"diskAuditMode={material.GetFloat("_DiskAuditMode"):F1}, " +
                $"basisR={material.GetVector("_LensWorldRight")}, " +
                $"basisU={material.GetVector("_LensWorldUp")}, " +
                $"basisF={material.GetVector("_LensWorldForward")}."
            );
        }

        private static void Capture(GateOptions options, string fileName, int width, int height)
        {
            var camera = Camera.main;
            if (camera == null)
            {
                throw new MissingReferenceException("Main Camera not found.");
            }

            foreach (var skyShell in UnityEngine.Object.FindObjectsByType<BlackHoleXrSkyShell>())
            {
                if (skyShell != null && skyShell.gameObject.activeInHierarchy)
                {
                    skyShell.SyncNow();
                }
            }

            foreach (var lensMap in UnityEngine.Object.FindObjectsByType<BlackHoleLensMap>())
            {
                if (lensMap == null || !lensMap.gameObject.activeInHierarchy)
                {
                    continue;
                }
                var renderer = lensMap.GetComponent<MeshRenderer>();
                if (renderer != null && renderer.sharedMaterial != null)
                {
                    lensMap.ApplyToMaterial(renderer.sharedMaterial);
                }
            }

            Directory.CreateDirectory(options.CaptureDir);
            string path = Path.Combine(options.CaptureDir, fileName);
            float oldAspect = camera.aspect;
            var oldTarget = camera.targetTexture;
            var oldActive = RenderTexture.active;

            var target = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32)
            {
                antiAliasing = 1
            };
            var texture = new Texture2D(width, height, TextureFormat.RGBA32, mipChain: false, linear: false);
            try
            {
                camera.aspect = (float)width / height;
                camera.targetTexture = target;
                camera.Render();
                RenderTexture.active = target;
                texture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                texture.Apply(updateMipmaps: false, makeNoLongerReadable: false);
                File.WriteAllBytes(path, texture.EncodeToPNG());
                Debug.Log($"GR-BH-XR gate capture wrote {path}");
            }
            finally
            {
                camera.aspect = oldAspect;
                camera.targetTexture = oldTarget;
                RenderTexture.active = oldActive;
                UnityEngine.Object.DestroyImmediate(texture);
                target.Release();
                UnityEngine.Object.DestroyImmediate(target);
            }
        }

        private static void CaptureYaw(GateOptions options, float yawDeg, string fileName, int width, int height)
        {
            var camera = Camera.main;
            if (camera == null)
            {
                throw new MissingReferenceException("Main Camera not found.");
            }
            camera.transform.rotation = Quaternion.Euler(0.0f, yawDeg, 0.0f);
            Debug.Log($"GR-BH-XR angular yaw capture: yaw={yawDeg:F1} deg, file={fileName}");
            Capture(options, fileName, width, height);
        }

        private static Cubemap EnsureQuadrantCubemap(string path)
        {
            return EnsureProceduralCubemap(path, QuadrantColor);
        }

        private static Cubemap EnsureProtractorCubemap(string path)
        {
            return EnsureProceduralCubemap(path, ProtractorColor);
        }

        private static Cubemap EnsureProceduralCubemap(string path, Func<Vector3, Color> colorForDirection)
        {
            var cubemap = AssetDatabase.LoadAssetAtPath<Cubemap>(path);
            if (cubemap != null)
            {
                cubemap.filterMode = FilterMode.Point;
                cubemap.wrapMode = TextureWrapMode.Clamp;
                return cubemap;
            }

            EnsureFolder(Path.GetDirectoryName(path)?.Replace('\\', '/') ?? "Assets/GRBHXR/Skyboxes");
            const int size = 64;
            cubemap = new Cubemap(size, TextureFormat.RGBA32, mipChain: false)
            {
                name = Path.GetFileNameWithoutExtension(path),
                filterMode = FilterMode.Point,
                wrapMode = TextureWrapMode.Clamp
            };
            var faces = new[]
            {
                CubemapFace.PositiveX,
                CubemapFace.NegativeX,
                CubemapFace.PositiveY,
                CubemapFace.NegativeY,
                CubemapFace.PositiveZ,
                CubemapFace.NegativeZ
            };
            foreach (CubemapFace face in faces)
            {
                var pixels = new Color[size * size];
                for (int y = 0; y < size; y += 1)
                {
                    for (int x = 0; x < size; x += 1)
                    {
                        float u = 2.0f * ((x + 0.5f) / size) - 1.0f;
                        float v = 2.0f * ((y + 0.5f) / size) - 1.0f;
                        pixels[y * size + x] = colorForDirection(DirectionForFace(face, u, v));
                    }
                }
                cubemap.SetPixels(pixels, face);
            }
            cubemap.Apply(updateMipmaps: false, makeNoLongerReadable: false);
            AssetDatabase.CreateAsset(cubemap, path);
            AssetDatabase.SaveAssets();
            return cubemap;
        }

        private static Material EnsureSkyboxMaterial(string path, Cubemap cubemap)
        {
            var material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material == null)
            {
                EnsureFolder(Path.GetDirectoryName(path)?.Replace('\\', '/') ?? "Assets/GRBHXR/Skyboxes");
                var shader = Shader.Find("Skybox/Cubemap");
                if (shader == null)
                {
                    throw new MissingReferenceException("Shader not found: Skybox/Cubemap");
                }
                material = new Material(shader) { name = Path.GetFileNameWithoutExtension(path) };
                AssetDatabase.CreateAsset(material, path);
            }
            material.SetTexture("_Tex", cubemap);
            EditorUtility.SetDirty(material);
            AssetDatabase.SaveAssets();
            return material;
        }

        private static Vector3 DirectionForFace(CubemapFace face, float u, float v)
        {
            switch (face)
            {
                case CubemapFace.PositiveX:
                    return new Vector3(1.0f, -v, -u).normalized;
                case CubemapFace.NegativeX:
                    return new Vector3(-1.0f, -v, u).normalized;
                case CubemapFace.PositiveY:
                    return new Vector3(u, 1.0f, v).normalized;
                case CubemapFace.NegativeY:
                    return new Vector3(u, -1.0f, -v).normalized;
                case CubemapFace.PositiveZ:
                    return new Vector3(u, -v, 1.0f).normalized;
                case CubemapFace.NegativeZ:
                    return new Vector3(-u, -v, -1.0f).normalized;
                default:
                    return Vector3.forward;
            }
        }

        private static Color QuadrantColor(Vector3 direction)
        {
            if (direction.x >= 0.0f && direction.y >= 0.0f)
            {
                return Color.red;
            }
            if (direction.x < 0.0f && direction.y >= 0.0f)
            {
                return Color.green;
            }
            if (direction.x < 0.0f && direction.y < 0.0f)
            {
                return Color.blue;
            }
            return Color.yellow;
        }

        private static Color ProtractorColor(Vector3 direction)
        {
            float thetaDeg = Mathf.Acos(Mathf.Clamp(direction.z, -1.0f, 1.0f)) * Mathf.Rad2Deg;
            int band = Mathf.Clamp(Mathf.FloorToInt(thetaDeg / 10.0f), 0, 17);
            float encoded = (band + 0.5f) / 18.0f;
            return new Color(encoded, 0.0f, 1.0f - encoded, 1.0f);
        }

        private static T LoadRequired<T>(string path) where T : UnityEngine.Object
        {
            var asset = AssetDatabase.LoadAssetAtPath<T>(path);
            if (asset == null)
            {
                throw new MissingReferenceException($"Required asset not found: {path}");
            }
            return asset;
        }

        private static void AssignSerializedObject(UnityEngine.Object target, string fieldName, UnityEngine.Object value)
        {
            var serializedObject = new SerializedObject(target);
            var property = serializedObject.FindProperty(fieldName);
            if (property == null)
            {
                throw new MissingReferenceException($"Serialized field not found: {target.GetType().Name}.{fieldName}");
            }
            property.objectReferenceValue = value;
            serializedObject.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(target);
        }

        private static void AssignSerializedBool(UnityEngine.Object target, string fieldName, bool value)
        {
            var serializedObject = new SerializedObject(target);
            var property = serializedObject.FindProperty(fieldName);
            if (property == null)
            {
                throw new MissingReferenceException($"Serialized field not found: {target.GetType().Name}.{fieldName}");
            }
            property.boolValue = value;
            serializedObject.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(target);
        }

        private static void AssignSerializedFloat(UnityEngine.Object target, string fieldName, float value)
        {
            var serializedObject = new SerializedObject(target);
            var property = serializedObject.FindProperty(fieldName);
            if (property == null)
            {
                throw new MissingReferenceException($"Serialized field not found: {target.GetType().Name}.{fieldName}");
            }
            property.floatValue = value;
            serializedObject.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(target);
        }

        private static void AssignSerializedInt(UnityEngine.Object target, string fieldName, int value)
        {
            var serializedObject = new SerializedObject(target);
            var property = serializedObject.FindProperty(fieldName);
            if (property == null)
            {
                throw new MissingReferenceException($"Serialized field not found: {target.GetType().Name}.{fieldName}");
            }
            property.intValue = value;
            serializedObject.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(target);
        }

        private static void AssignSerializedVector3(UnityEngine.Object target, string fieldName, Vector3 value)
        {
            var serializedObject = new SerializedObject(target);
            var property = serializedObject.FindProperty(fieldName);
            if (property == null)
            {
                throw new MissingReferenceException($"Serialized field not found: {target.GetType().Name}.{fieldName}");
            }
            property.vector3Value = value;
            serializedObject.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(target);
        }

        private static void EnsureFolder(string path)
        {
            if (string.IsNullOrEmpty(path) || AssetDatabase.IsValidFolder(path))
            {
                return;
            }

            var parent = Path.GetDirectoryName(path)?.Replace('\\', '/');
            var name = Path.GetFileName(path);
            if (string.IsNullOrEmpty(parent) || string.IsNullOrEmpty(name))
            {
                return;
            }
            EnsureFolder(parent);
            if (!AssetDatabase.IsValidFolder(path))
            {
                AssetDatabase.CreateFolder(parent, name);
            }
        }

        private sealed class GateOptions
        {
            public string LensMapDir = DefaultLensMapDir;
            public string CubemapPath = DefaultCubemapPath;
            public string SkyboxMaterialPath = DefaultSkyboxMaterialPath;
            public string QuadrantCubemapPath = DefaultQuadrantCubemapPath;
            public string QuadrantSkyboxMaterialPath = DefaultQuadrantSkyboxMaterialPath;
            public string ProtractorCubemapPath = DefaultProtractorCubemapPath;
            public string ProtractorSkyboxMaterialPath = DefaultProtractorSkyboxMaterialPath;
            public string MaterialPath = DefaultMaterialPath;
            public string ScenePath = DefaultScenePath;
            public string FullSkyTransferDir = DefaultFullSkyTransferDir;
            public string CaptureDir = DefaultCaptureDir;
            public bool UseAngularWindow;
            public bool UseSkyShell;
            public bool ShowControlPanel;
            public bool DiskVisualMode;
            public float DiskAuditMode;

            public static GateOptions FromCommandLine()
            {
                var options = new GateOptions();
                options.LensMapDir = CommandLineValue("-grbhxrLensMapDir", options.LensMapDir);
                options.CubemapPath = CommandLineValue("-grbhxrCubemapPath", options.CubemapPath);
                options.SkyboxMaterialPath = CommandLineValue("-grbhxrSkyboxMaterialPath", options.SkyboxMaterialPath);
                options.QuadrantCubemapPath = CommandLineValue("-grbhxrQuadrantCubemapPath", options.QuadrantCubemapPath);
                options.QuadrantSkyboxMaterialPath = CommandLineValue("-grbhxrQuadrantSkyboxMaterialPath", options.QuadrantSkyboxMaterialPath);
                options.ProtractorCubemapPath = CommandLineValue("-grbhxrProtractorCubemapPath", options.ProtractorCubemapPath);
                options.ProtractorSkyboxMaterialPath = CommandLineValue("-grbhxrProtractorSkyboxMaterialPath", options.ProtractorSkyboxMaterialPath);
                options.MaterialPath = CommandLineValue("-grbhxrMaterialPath", options.MaterialPath);
                options.ScenePath = CommandLineValue("-grbhxrScenePath", options.ScenePath);
                options.FullSkyTransferDir = CommandLineValue("-grbhxrFullSkyTransferDir", options.FullSkyTransferDir);
                options.CaptureDir = CommandLineValue("-grbhxrCaptureDir", options.CaptureDir);
                options.UseAngularWindow = CommandLineFlag("-grbhxrUseAngularWindow");
                options.UseSkyShell = CommandLineFlag("-grbhxrUseSkyShell");
                options.ShowControlPanel = CommandLineFlag("-grbhxrShowControlPanel");
                options.DiskVisualMode = CommandLineFlag("-grbhxrDiskVisualMode");
                options.DiskAuditMode = CommandLineFloat("-grbhxrDiskAuditMode", options.DiskAuditMode);
                return options;
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

            private static float CommandLineFloat(string key, float fallback)
            {
                string value = CommandLineValue(key, "");
                if (string.IsNullOrWhiteSpace(value))
                {
                    return fallback;
                }
                return float.TryParse(value, out float parsed) ? parsed : fallback;
            }

            private static bool CommandLineFlag(string key)
            {
                var args = Environment.GetCommandLineArgs();
                foreach (var arg in args)
                {
                    if (string.Equals(arg, key, StringComparison.OrdinalIgnoreCase))
                    {
                        return true;
                    }
                }
                return false;
            }
        }

        private enum GateSkyboxKind
        {
            Nasa,
            Quadrant,
            Protractor
        }
    }
}
