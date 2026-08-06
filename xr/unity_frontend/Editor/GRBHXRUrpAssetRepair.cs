using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEditor;
using UnityEditor.Rendering;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace GRBHXR.EditorTools
{
    // Repairs URP render pipeline assets that were serialized by a newer editor
    // than the one this project is locked to.
    //
    // Failure mode this exists for: Unity 6000.5 / URP 17.5.0 writes
    // UniversalRenderPipelineGlobalSettings.m_AssetVersion = 10 and
    // UniversalRenderPipelineAsset.k_AssetVersion = 13. URP 17.0.4 expects 8 and
    // 12. Both URP migration ladders are `if (version < N)` chains with no else
    // branch, so a higher serialized version is a silent no-op: the asset loads,
    // nothing throws, and IsAtLastVersion() stays false forever. URP's own
    // URPBuildDataValidator then fails every player build with a
    // BuildFailedException, and neither IsAtLastVersion() nor the version fields
    // are reachable from an external assembly.
    //
    // Repair strategy: never write a version field. Build a pristine asset with
    // the public factory for the INSTALLED URP version, carry the project's
    // settings across it, then copy that pristine object over the existing asset
    // with EditorUtility.CopySerialized. The corrected version number arrives as
    // a property of a correctly constructed object, not as an edit. Because the
    // existing asset object is written in place, its GUID and asset path survive,
    // so GraphicsSettings and QualitySettings registrations are not disturbed.
    //
    // Verified against the locked packages in this project's Library/PackageCache:
    //   com.unity.render-pipelines.universal 17.0.4
    //   com.unity.render-pipelines.core      17.0.4
    // UniversalRenderPipelineGlobalSettings is `internal` in 17.0.4
    // (Runtime/UniversalRenderPipelineGlobalSettings.cs:22) and its Ensure()
    // overload is `internal static` (same file:239), so neither is callable from
    // this assembly. RenderPipelineGlobalSettingsUtils.Create(Type, path, source)
    // (core Runtime/RenderPipeline/RenderPipelineGlobalSettingsUtils.cs:35) is the
    // public equivalent and is used instead; the Type overload avoids having to
    // name the internal type.
    public static class GRBHXRUrpAssetRepair
    {
        private const string LogPrefix = "GR-BH-XR URP asset repair";
        private const string RepairMenuPath = "GR-BH-XR/URP Asset Repair/Repair URP Assets For Installed Editor";
        private const string AuditMenuPath = "GR-BH-XR/URP Asset Repair/Audit URP Assets";
        private const string PreflightMenuPath = "GR-BH-XR/URP Asset Repair/Preflight URP Assets (Fail Closed)";
        private const string RepairBatchMethod = "GRBHXR.EditorTools.GRBHXRUrpAssetRepair.BatchRepairUrpAssets";

        // URP 17.0.4 writes this exact path unconditionally whenever a global
        // settings object is constructed with no default volume profile assigned:
        // UniversalRenderPipelineGlobalSettings.Initialize ->
        // GetOrCreateDefaultVolumeProfile -> AssetDatabase.CreateAsset. That fires
        // for the throwaway instance used to discover the expected asset version and
        // for RenderPipelineGlobalSettingsUtils.Create, so audit, preflight and
        // repair all have to bracket their work and remove the transient asset.
        private const string UrpDefaultVolumeProfilePath = "Assets/DefaultVolumeProfile.asset";

        private const string GlobalSettingsVersionProperty = "m_AssetVersion";
        private const string RenderPipelineAssetVersionProperty = "k_AssetVersion";
        private const string GlobalSettingsContainerProperty = "m_Settings";

        private const string ReportSchema = "grbhxr.urp_asset_repair/2";
        private const string ReportDirArgument = "-grbhxrUrpRepairReportDir";
        private const string FailureInjectionArgument = "-grbhxrUrpRepairTestFailAfterAssets";

        // Serialized properties that must never be carried from the incompatible
        // asset into the pristine one. The version fields are the whole point of
        // the repair; the rest are object identity.
        private static readonly string[] BlockedPropertyPaths =
        {
            "m_AssetVersion",
            "k_AssetVersion",
            "k_AssetPreviousVersion",
            "m_ObjectHideFlags",
            "m_CorrespondingSourceObject",
            "m_PrefabInstance",
            "m_PrefabAsset",
            "m_GameObject",
            "m_Enabled",
            "m_EditorHideFlags",
            "m_Script",
            "m_Name",
            "m_EditorClassIdentifier"
        };

        // Does not modify any render pipeline asset. It does construct one throwaway
        // global settings object to discover the version the installed URP expects,
        // which makes URP create UrpDefaultVolumeProfilePath; that transient is
        // removed again before this returns.
        [MenuItem(AuditMenuPath)]
        public static void AuditUrpAssets()
        {
            var report = new UrpRepairReport { mode = "audit" };
            PopulateEnvironment(report);

            var notes = new List<string>();
            BeginUrpConstructionScope();
            try
            {
                report.before = ProbeAll();
            }
            finally
            {
                EndUrpConstructionScope(notes);
            }

            report.after = report.before;
            report.actions = notes.ToArray();
            report.compatibleAfter = AllCompatible(report.before);
            string reportPath = WriteReport(report);

            foreach (string note in notes)
            {
                Debug.Log($"{LogPrefix} audit note: {note}");
            }

            Debug.Log(
                $"{LogPrefix} audit complete: " +
                $"unityVersion={report.unityVersion}, projectEditorVersion={report.projectEditorVersion}, " +
                $"urpPackageVersion={report.urpPackageVersion}, assets={report.before.Length}, " +
                $"compatible={report.compatibleAfter}, report={reportPath}"
            );
            foreach (UrpAssetProbe probe in report.before)
            {
                Debug.Log($"{LogPrefix} audit asset: {Describe(probe)}");
            }
        }

        public static void BatchAuditUrpAssets()
        {
            AuditUrpAssets();
        }

        [MenuItem(PreflightMenuPath)]
        public static void PreflightUrpAssets()
        {
            AssertProjectUrpAssetsCompatible();
            Debug.Log($"{LogPrefix} preflight passed: all render pipeline assets match the installed editor.");
        }

        public static void BatchPreflightUrpAssets()
        {
            PreflightUrpAssets();
        }

        // Fail-closed gate for build and any other entry point that must not run
        // against assets from a different editor. This never repairs anything.
        public static void AssertProjectUrpAssetsCompatible()
        {
            AssertEditorVersionMatchesProject();

            var notes = new List<string>();
            UrpAssetProbe[] probes;
            BeginUrpConstructionScope();
            try
            {
                probes = ProbeAll();
            }
            finally
            {
                EndUrpConstructionScope(notes);
            }
            foreach (string note in notes)
            {
                Debug.Log($"{LogPrefix} preflight note: {note}");
            }

            if (probes.Length == 0)
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} preflight failed: no URP render pipeline asset is registered for this project. " +
                    "Assign a Universal Render Pipeline asset in Project Settings > Graphics before building."
                );
            }

            var incompatible = new List<UrpAssetProbe>();
            foreach (UrpAssetProbe probe in probes)
            {
                if (!probe.compatible)
                {
                    incompatible.Add(probe);
                }
            }

            if (incompatible.Count == 0)
            {
                return;
            }

            var message = new System.Text.StringBuilder();
            message.Append($"{LogPrefix} preflight failed: {incompatible.Count} render pipeline asset(s) ");
            message.Append("were serialized by a different editor version than this project is locked to.");
            foreach (UrpAssetProbe probe in incompatible)
            {
                message.Append(Environment.NewLine);
                message.Append("  - ");
                message.Append(Describe(probe));
            }
            message.Append(Environment.NewLine);
            message.Append($"Run the menu item '{RepairMenuPath}', or in batch mode:");
            message.Append(Environment.NewLine);
            message.Append($"  Unity.exe -batchmode -quit -projectPath <project> -executeMethod {RepairBatchMethod}");
            message.Append(Environment.NewLine);
            message.Append("Scene setup and the player build never repair these assets automatically.");
            throw new InvalidOperationException(message.ToString());
        }

        [MenuItem(RepairMenuPath)]
        public static void RepairUrpAssets()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isPlaying || EditorApplication.isPaused)
            {
                throw new InvalidOperationException("Exit Play mode before repairing render pipeline assets.");
            }

            AssertEditorVersionMatchesProject();

            var report = new UrpRepairReport { mode = "repair" };
            PopulateEnvironment(report);

            var actions = new List<string>();
            var preserved = new List<string>();
            var deliberateDefaults = new List<string>();

            BeginUrpConstructionScope();
            try
            {
                try
                {
                    report.before = ProbeAll();

                    string backupDirectory = Path.Combine(ReportDirectory(), $"pre_repair_{report.timestampUtc}");
                    Directory.CreateDirectory(backupDirectory);
                    report.backupDirectory = backupDirectory.Replace('\\', '/');

                    // A repair is transactional: every incompatible asset is backed up
                    // before the first serialized object is changed.
                    foreach (UrpAssetProbe probe in report.before)
                    {
                        if (!probe.compatible)
                        {
                            BackupAssetFile(probe.assetPath, backupDirectory);
                        }
                    }

                    int failAfterAssets = CommandLineIntValue(FailureInjectionArgument, 0);
                    int repairedAssets = 0;
                    foreach (UrpAssetProbe probe in report.before)
                    {
                        if (probe.compatible)
                        {
                            actions.Add($"skipped {probe.assetPath}: already at version {probe.serializedVersion}");
                            continue;
                        }

                        if (probe.role == "globalSettings")
                        {
                            RepairGlobalSettings(probe, actions, preserved, deliberateDefaults);
                        }
                        else
                        {
                            RepairRenderPipelineAsset(probe, actions, preserved, deliberateDefaults);
                        }
                        repairedAssets += 1;
                        if (failAfterAssets > 0 && repairedAssets >= failAfterAssets)
                        {
                            throw new InvalidOperationException(
                                $"{LogPrefix} injected validation failure after {repairedAssets} repaired asset(s)."
                            );
                        }
                    }

                    AssetDatabase.SaveAssets();
                    AssetDatabase.Refresh();

                    // Probed inside the scope so the transient volume profile URP creates
                    // is removed once, after both probe passes, rather than left behind.
                    report.after = ProbeAll();
                    report.compatibleAfter = AllCompatible(report.after);
                    report.registrationsChanged = RegistrationsChanged(report.before, report.after);
                    if (!report.compatibleAfter)
                    {
                        throw new InvalidOperationException(
                            $"{LogPrefix} repair did not converge. Assets are still incompatible with the installed editor."
                        );
                    }
                    if (report.registrationsChanged)
                    {
                        throw new InvalidOperationException(
                            $"{LogPrefix} changed a GraphicsSettings or QualitySettings asset registration."
                        );
                    }
                }
                finally
                {
                    // Keep cleanup inside the transaction boundary. A leftover
                    // URP-created asset is a failed repair and must trigger rollback.
                    EndUrpConstructionScope(actions);
                }
            }
            catch (Exception repairFailure)
            {
                report.failure = repairFailure.ToString();
                if (!string.IsNullOrEmpty(report.backupDirectory))
                {
                    try
                    {
                        RestoreBackups(report.before, report.backupDirectory, actions);
                        report.rollbackPerformed = true;
                    }
                    catch (Exception rollbackFailure)
                    {
                        report.failure += Environment.NewLine + "ROLLBACK FAILURE:" + Environment.NewLine + rollbackFailure;
                        report.actions = actions.ToArray();
                        string rollbackReportPath = WriteReport(report);
                        throw new AggregateException(
                            $"{LogPrefix} failed and rollback also failed. Inspect {rollbackReportPath} and restore " +
                            $"the pre-repair copies from {report.backupDirectory} before opening the project again.",
                            repairFailure,
                            rollbackFailure
                        );
                    }
                }
                report.actions = actions.ToArray();
                report.preservedValues = preserved.ToArray();
                report.deliberateDefaults = deliberateDefaults.ToArray();
                string failedReportPath = WriteReport(report);
                throw new InvalidOperationException(
                    $"{LogPrefix} failed and restored every backed-up render-pipeline asset. " +
                    $"The failure report is at {failedReportPath}.",
                    repairFailure
                );
            }

            report.actions = actions.ToArray();
            report.preservedValues = preserved.ToArray();
            report.deliberateDefaults = deliberateDefaults.ToArray();
            string reportPath = WriteReport(report);

            foreach (UrpAssetProbe probe in report.before)
            {
                Debug.Log($"{LogPrefix} pre-repair: {Describe(probe)}");
            }
            foreach (UrpAssetProbe probe in report.after)
            {
                Debug.Log($"{LogPrefix} post-repair: {Describe(probe)}");
            }
            foreach (string entry in report.actions)
            {
                Debug.Log($"{LogPrefix} action: {entry}");
            }
            foreach (string entry in preserved)
            {
                Debug.Log($"{LogPrefix} preserved: {entry}");
            }
            foreach (string entry in deliberateDefaults)
            {
                Debug.LogWarning($"{LogPrefix} deliberate default: {entry}");
            }
            Debug.Log(
                $"{LogPrefix} repair complete: assets={report.after.Length}, " +
                $"compatible={report.compatibleAfter}, registrationsChanged={report.registrationsChanged}, " +
                $"backup={report.backupDirectory}, report={reportPath}"
            );

        }

        public static void BatchRepairUrpAssets()
        {
            RepairUrpAssets();
        }

        private static void RepairGlobalSettings(
            UrpAssetProbe probe,
            List<string> actions,
            List<string> preserved,
            List<string> deliberateDefaults
        )
        {
            RenderPipelineGlobalSettings existing =
                EditorGraphicsSettings.GetRenderPipelineGlobalSettingsAsset<UniversalRenderPipeline>();
            if (existing == null)
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} cannot repair global settings: no URP global settings asset is registered."
                );
            }

            string existingPath = AssetDatabase.GetAssetPath(existing);
            string existingName = existing.name;
            string directory = Path.GetDirectoryName(existingPath)?.Replace('\\', '/');
            if (string.IsNullOrEmpty(directory))
            {
                directory = "Assets/Settings";
            }
            VolumeProfile previousVolumeProfile = ReadDefaultVolumeProfile();
            Dictionary<string, UnityEngine.Object> previousProjectReferences =
                CollectProjectAssetReferences(existing);

            // RenderPipelineGlobalSettingsUtils.Create writes an asset to disk, so
            // both scratch instances are removed after the repaired object has been
            // copied over the registered asset. The first clone uses the damaged
            // asset as a data source: Unity drops managed-reference types absent from
            // the installed URP while retaining every compatible setting value. The
            // second clone supplies the installed editor's authoritative asset
            // version and default settings layout.
            string scratchPath = $"{directory}/GRBHXR_UrpGlobalSettings_Pristine.asset";
            string sanitizedPath = $"{directory}/GRBHXR_UrpGlobalSettings_Sanitized.asset";
            RenderPipelineGlobalSettings sanitized = null;
            RenderPipelineGlobalSettings pristine = null;
            string sanitizedAssetPath = null;
            string pristinePath = null;

            try
            {
                sanitized = RenderPipelineGlobalSettingsUtils.Create(existing.GetType(), sanitizedPath, existing);
                if (sanitized == null)
                {
                    throw new InvalidOperationException(
                        $"{LogPrefix} failed to sanitize compatible settings from {existingPath}."
                    );
                }
                sanitizedAssetPath = AssetDatabase.GetAssetPath(sanitized);

                pristine = RenderPipelineGlobalSettingsUtils.Create(existing.GetType(), scratchPath);
                if (pristine == null)
                {
                    throw new InvalidOperationException(
                        $"{LogPrefix} failed to create a pristine {existing.GetType().Name} for the installed URP version."
                    );
                }
                pristinePath = AssetDatabase.GetAssetPath(pristine);

                int pristineVersion = ReadIntProperty(pristine, GlobalSettingsVersionProperty);
                if (pristineVersion != probe.expectedVersion)
                {
                    throw new InvalidOperationException(
                        $"{LogPrefix} refusing to repair: a freshly created {existing.GetType().Name} reports " +
                        $"{GlobalSettingsVersionProperty}={pristineVersion} but the expected version was probed as " +
                        $"{probe.expectedVersion}. The installed URP version could not be determined safely."
                    );
                }

                if (SerializationUtility.HasManagedReferencesWithMissingTypes(sanitized))
                {
                    throw new InvalidOperationException(
                        $"{LogPrefix} sanitized clone for {existingPath} still contains managed-reference types " +
                        "that do not exist in the installed URP. Refusing to guess at a partial settings migration."
                    );
                }

                RemoveNullManagedSettings(sanitized);
                int managedSettingsCopied = CopyCompatibleManagedSettings(sanitized, pristine, existingPath);
                preserved.Add(
                    $"{existingPath}: preserved and byte-verified {managedSettingsCopied} compatible " +
                    "render-pipeline graphics settings by managed-reference type"
                );

                // Top-level fields are copied separately. The settings container is
                // blocked here because it has already been migrated type-by-type;
                // copying the original container would reintroduce the newer editor's
                // missing types.
                int copied = CopyTopLevelProperties(
                    existing,
                    pristine,
                    new[] { GlobalSettingsContainerProperty },
                    preserved,
                    $"globalSettings {existingPath}"
                );
                actions.Add($"carried {copied} top-level serialized properties into the pristine global settings");

                // Keep a typed post-write check for the project default profile in
                // addition to the exact managed-setting comparison. It is a
                // load-bearing project asset and should fail closed if URP's global
                // registration changed while scratch assets were created.
                // Missing managed references are tracked per object, so clear the
                // stale ones on the registered asset before overwriting it.
                if (SerializationUtility.HasManagedReferencesWithMissingTypes(existing))
                {
                    SerializationUtility.ClearAllManagedReferencesWithMissingTypes(existing);
                    actions.Add($"cleared missing [SerializeReference] entries on {existingPath}");
                }

                EditorUtility.CopySerialized(pristine, existing);
                existing.name = existingName;
                EditorUtility.SetDirty(existing);
                AssetDatabase.SaveAssetIfDirty(existing);
                AssertManagedSettingsEqual(pristine, existing, existingPath);
                actions.Add(
                    $"rewrote {existingPath} in place from a pristine {existing.GetType().Name}; " +
                    $"guid preserved as {AssetDatabase.AssetPathToGUID(existingPath)}"
                );

                // Re-registering is a no-op when the asset object is unchanged, but it
                // is cheap insurance against URP's global settings postprocessor having
                // pointed the map somewhere else while the scratch asset existed.
                EditorGraphicsSettings.SetRenderPipelineGlobalSettingsAsset<UniversalRenderPipeline>(existing);

                RestoreDefaultVolumeProfile(previousVolumeProfile, existing, existingPath, preserved, deliberateDefaults);
                ReportProjectAssetReferenceLosses(
                    previousProjectReferences,
                    existing,
                    existingPath,
                    preserved,
                    deliberateDefaults
                );

                if (probe.missingManagedReferenceTypes.Length > 0)
                {
                    deliberateDefaults.Add(
                        $"{existingPath}: discarded only the {probe.missingManagedReferenceTypes.Length} " +
                        "managed-reference types unavailable in the installed URP: " +
                        string.Join(" | ", probe.missingManagedReferenceTypes)
                    );
                }
            }
            finally
            {
                EditorGraphicsSettings.SetRenderPipelineGlobalSettingsAsset<UniversalRenderPipeline>(existing);
                DeleteScratchAssetOrThrow(pristinePath, existingPath);
                DeleteScratchAssetOrThrow(sanitizedAssetPath, existingPath);
            }
        }

        private static void RepairRenderPipelineAsset(
            UrpAssetProbe probe,
            List<string> actions,
            List<string> preserved,
            List<string> deliberateDefaults
        )
        {
            var existing = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(probe.assetPath);
            if (existing == null)
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} cannot repair render pipeline asset: {probe.assetPath} did not load as a " +
                    "UniversalRenderPipelineAsset."
                );
            }

            ReadOnlySpan<ScriptableRendererData> rendererDataList = existing.rendererDataList;
            ScriptableRendererData rendererData = null;
            for (int index = 0; index < rendererDataList.Length; index += 1)
            {
                if (rendererDataList[index] == null)
                {
                    throw new InvalidOperationException(
                        $"{LogPrefix} refusing to repair {probe.assetPath}: renderer data slot {index} is null. " +
                        "Repairing would make a project-authored renderer substitution ambiguous."
                    );
                }
                if (rendererData == null)
                {
                    rendererData = rendererDataList[index];
                }
            }
            if (rendererData == null)
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} refusing to repair {probe.assetPath}: it has no renderer data to preserve. " +
                    "Repairing would silently substitute a newly created renderer."
                );
            }

            string[] expectedRendererPaths = DescribeRendererData(existing);
            int expectedDefaultRendererIndex = ReadIntProperty(existing, "m_DefaultRendererIndex");

            string existingName = existing.name;
            UniversalRenderPipelineAsset pristine = UniversalRenderPipelineAsset.Create(rendererData);
            if (pristine == null)
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} failed to create a pristine UniversalRenderPipelineAsset for the installed URP version."
                );
            }

            try
            {
                int pristineVersion = ReadIntProperty(pristine, RenderPipelineAssetVersionProperty);
                if (pristineVersion != probe.expectedVersion)
                {
                    throw new InvalidOperationException(
                        $"{LogPrefix} refusing to repair: a freshly created UniversalRenderPipelineAsset reports " +
                        $"{RenderPipelineAssetVersionProperty}={pristineVersion} but the expected version was probed as " +
                        $"{probe.expectedVersion}. The installed URP version could not be determined safely."
                    );
                }

                int copied = CopyTopLevelProperties(
                    existing,
                    pristine,
                    new string[0],
                    preserved,
                    $"renderPipelineAsset {probe.assetPath}"
                );
                actions.Add(
                    $"carried {copied} top-level serialized properties into the pristine render pipeline asset " +
                    $"for {probe.assetPath}"
                );

                // The six URP 17.5.0-only keys (m_ReflectionProbeAtlas and the five
                // m_Prefilter* additions) are already absent from the loaded object:
                // URP 17.0.4 drops unknown YAML keys at deserialize time, so copying
                // property-by-property cannot reintroduce them.
                deliberateDefaults.Add(
                    $"{probe.assetPath}: serialized keys unknown to the installed URP version were not carried across " +
                    "(they were already dropped when this editor deserialized the asset)"
                );

                EditorUtility.CopySerialized(pristine, existing);
                existing.name = existingName;
                EditorUtility.SetDirty(existing);
                AssetDatabase.SaveAssetIfDirty(existing);
                actions.Add(
                    $"rewrote {probe.assetPath} in place from a pristine UniversalRenderPipelineAsset; " +
                    $"guid preserved as {AssetDatabase.AssetPathToGUID(probe.assetPath)}"
                );
                AssertRendererDataPreserved(
                    existing,
                    expectedRendererPaths,
                    expectedDefaultRendererIndex,
                    probe.assetPath
                );
                preserved.Add(
                    $"{probe.assetPath}: preserved all {expectedRendererPaths.Length} renderer data slots and " +
                    $"default renderer index {expectedDefaultRendererIndex}"
                );
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(pristine);
            }
        }

        // Copies every top-level serialized property from source to destination
        // except identity fields and the version fields. Returns the number copied.
        private static int CopyTopLevelProperties(
            UnityEngine.Object source,
            UnityEngine.Object destination,
            string[] additionalBlocked,
            List<string> preserved,
            string label
        )
        {
            var sourceObject = new SerializedObject(source);
            var destinationObject = new SerializedObject(destination);
            SerializedProperty iterator = sourceObject.GetIterator();
            int copied = 0;
            int skipped = 0;

            bool enterChildren = true;
            while (iterator.Next(enterChildren))
            {
                enterChildren = false;
                string path = iterator.propertyPath;
                if (IsBlocked(path, additionalBlocked))
                {
                    skipped += 1;
                    continue;
                }
                if (destinationObject.FindProperty(path) == null)
                {
                    skipped += 1;
                    continue;
                }
                destinationObject.CopyFromSerializedProperty(iterator);
                copied += 1;
            }

            destinationObject.ApplyModifiedPropertiesWithoutUndo();
            preserved.Add($"{label}: carried {copied} serialized properties, withheld {skipped}");
            return copied;
        }

        private static void RemoveNullManagedSettings(UnityEngine.Object owner)
        {
            var serialized = new SerializedObject(owner);
            SerializedProperty list = serialized.FindProperty("m_Settings.m_SettingsList.m_List");
            if (list == null)
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} could not find the render-pipeline graphics settings list on {owner.name}."
                );
            }

            for (int index = list.arraySize - 1; index >= 0; index -= 1)
            {
                SerializedProperty element = list.GetArrayElementAtIndex(index);
                if (element.managedReferenceValue == null)
                {
                    list.DeleteArrayElementAtIndex(index);
                }
            }
            serialized.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(owner);
            AssetDatabase.SaveAssetIfDirty(owner);
        }

        // The data-source factory drops unavailable types but keeps compatible
        // managed settings. Copy those settings into the pristine installed-version
        // object by type, not by list index. EditorJsonUtility preserves serialized
        // scalar fields and Unity object references; an exact JSON round trip check
        // fails closed before the registered asset is touched.
        private static int CopyCompatibleManagedSettings(
            UnityEngine.Object source,
            UnityEngine.Object destination,
            string label
        )
        {
            Dictionary<string, object> sourceSettings = CollectManagedSettingsByType(source, label + " sanitized source");
            Dictionary<string, object> destinationSettings = CollectManagedSettingsByType(
                destination,
                label + " installed-version destination"
            );

            if (sourceSettings.Count != destinationSettings.Count)
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} refusing to repair {label}: sanitized source exposes {sourceSettings.Count} " +
                    $"compatible settings but the installed-version object exposes {destinationSettings.Count}."
                );
            }

            var expectedJson = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (KeyValuePair<string, object> entry in sourceSettings)
            {
                if (!destinationSettings.TryGetValue(entry.Key, out object destinationValue))
                {
                    throw new InvalidOperationException(
                        $"{LogPrefix} refusing to repair {label}: installed URP does not expose compatible setting " +
                        $"type {entry.Key}."
                    );
                }
                string json = EditorJsonUtility.ToJson(entry.Value, prettyPrint: false);
                EditorJsonUtility.FromJsonOverwrite(json, destinationValue);
                expectedJson.Add(entry.Key, json);
            }

            EditorUtility.SetDirty(destination);
            AssetDatabase.SaveAssetIfDirty(destination);

            Dictionary<string, object> verifiedSettings = CollectManagedSettingsByType(
                destination,
                label + " verified destination"
            );
            foreach (KeyValuePair<string, string> entry in expectedJson)
            {
                if (!verifiedSettings.TryGetValue(entry.Key, out object verifiedValue))
                {
                    throw new InvalidOperationException(
                        $"{LogPrefix} lost compatible setting {entry.Key} while repairing {label}."
                    );
                }
                string verifiedJson = EditorJsonUtility.ToJson(verifiedValue, prettyPrint: false);
                if (!string.Equals(entry.Value, verifiedJson, StringComparison.Ordinal))
                {
                    throw new InvalidOperationException(
                        $"{LogPrefix} changed serialized values for compatible setting {entry.Key} while repairing " +
                        $"{label}. Refusing to overwrite the registered asset."
                    );
                }
            }
            return expectedJson.Count;
        }

        private static Dictionary<string, object> CollectManagedSettingsByType(UnityEngine.Object owner, string label)
        {
            var serialized = new SerializedObject(owner);
            SerializedProperty list = serialized.FindProperty("m_Settings.m_SettingsList.m_List");
            if (list == null)
            {
                throw new InvalidOperationException($"{LogPrefix} could not find the settings list on {label}.");
            }

            var settings = new Dictionary<string, object>(StringComparer.Ordinal);
            for (int index = 0; index < list.arraySize; index += 1)
            {
                SerializedProperty element = list.GetArrayElementAtIndex(index);
                object value = element.managedReferenceValue;
                if (value == null)
                {
                    continue;
                }
                string typeName = element.managedReferenceFullTypename;
                if (string.IsNullOrEmpty(typeName) || settings.ContainsKey(typeName))
                {
                    throw new InvalidOperationException(
                        $"{LogPrefix} found an empty or duplicate managed setting type on {label}: '{typeName}'."
                    );
                }
                settings.Add(typeName, value);
            }
            return settings;
        }

        private static void AssertManagedSettingsEqual(
            UnityEngine.Object expected,
            UnityEngine.Object actual,
            string label
        )
        {
            Dictionary<string, object> expectedSettings = CollectManagedSettingsByType(expected, label + " expected");
            Dictionary<string, object> actualSettings = CollectManagedSettingsByType(actual, label + " actual");
            if (expectedSettings.Count != actualSettings.Count)
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} changed the compatible managed-setting count while writing {label}: " +
                    $"{expectedSettings.Count} -> {actualSettings.Count}."
                );
            }
            foreach (KeyValuePair<string, object> entry in expectedSettings)
            {
                if (!actualSettings.TryGetValue(entry.Key, out object actualValue) ||
                    !string.Equals(
                        EditorJsonUtility.ToJson(entry.Value, prettyPrint: false),
                        EditorJsonUtility.ToJson(actualValue, prettyPrint: false),
                        StringComparison.Ordinal
                    ))
                {
                    throw new InvalidOperationException(
                        $"{LogPrefix} changed compatible managed setting {entry.Key} while writing {label}."
                    );
                }
            }
        }

        private static bool IsBlocked(string propertyPath, string[] additionalBlocked)
        {
            foreach (string blocked in BlockedPropertyPaths)
            {
                if (string.Equals(propertyPath, blocked, StringComparison.Ordinal))
                {
                    return true;
                }
            }
            foreach (string blocked in additionalBlocked)
            {
                if (string.Equals(propertyPath, blocked, StringComparison.Ordinal))
                {
                    return true;
                }
            }
            return false;
        }

        // Constructing any URP global settings object -- the throwaway instance used
        // to discover the expected version, or the pristine asset built during a
        // repair -- makes URP 17.0.4 call AssetDatabase.CreateAsset on
        // UrpDefaultVolumeProfilePath unconditionally. CreateAsset replaces whatever
        // is already there and issues a new GUID, so refuse outright if a real asset
        // occupies that path rather than destroy it.
        private static void BeginUrpConstructionScope()
        {
            string absolutePath = Path.Combine(ProjectRoot(), UrpDefaultVolumeProfilePath);
            bool occupied = AssetDatabase.LoadMainAssetAtPath(UrpDefaultVolumeProfilePath) != null ||
                File.Exists(absolutePath);
            if (occupied)
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} refusing to run: {UrpDefaultVolumeProfilePath} already exists. Constructing a URP " +
                    "global settings object makes URP 17.0.4 write that exact path unconditionally, which would " +
                    "replace the existing asset and change its GUID, breaking every reference to it. Move or rename " +
                    "that asset first, then re-run."
                );
            }
        }

        private static void EndUrpConstructionScope(List<string> notes)
        {
            string absolutePath = Path.Combine(ProjectRoot(), UrpDefaultVolumeProfilePath);
            bool exists = AssetDatabase.LoadMainAssetAtPath(UrpDefaultVolumeProfilePath) != null ||
                File.Exists(absolutePath);
            if (!exists)
            {
                return;
            }

            if (AssetDatabase.DeleteAsset(UrpDefaultVolumeProfilePath) && !File.Exists(absolutePath))
            {
                notes.Add(
                    $"removed the transient {UrpDefaultVolumeProfilePath} that URP 17.0.4 creates whenever a global " +
                    "settings object is constructed"
                );
                return;
            }

            throw new InvalidOperationException(
                $"{LogPrefix} created transient {UrpDefaultVolumeProfilePath} but could not delete it. " +
                "The operation is not read-only and therefore cannot be accepted. Remove the transient asset and re-run."
            );
        }

        private static void DeleteScratchAssetOrThrow(string scratchPath, string protectedPath)
        {
            if (string.IsNullOrEmpty(scratchPath) || string.Equals(scratchPath, protectedPath, StringComparison.Ordinal))
            {
                return;
            }
            string absolutePath = Path.Combine(ProjectRoot(), scratchPath);
            bool exists = AssetDatabase.LoadMainAssetAtPath(scratchPath) != null || File.Exists(absolutePath);
            if (!exists)
            {
                return;
            }
            if (!AssetDatabase.DeleteAsset(scratchPath) || File.Exists(absolutePath))
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} could not delete scratch asset {scratchPath}. Refusing to report a clean repair."
                );
            }
        }

        // URPDefaultVolumeProfileSettings is public in URP 17.0.4 and implements the
        // public IDefaultVolumeProfileSettings, whose volumeProfile property has a
        // public setter. That is the supported way to read and restore the
        // project-wide default Volume without touching the [SerializeReference]
        // container by hand.
        private static VolumeProfile ReadDefaultVolumeProfile()
        {
            bool found = EditorGraphicsSettings
                .TryGetRenderPipelineSettingsForPipeline<URPDefaultVolumeProfileSettings, UniversalRenderPipeline>(
                    out URPDefaultVolumeProfileSettings settings
                );
            return found && settings != null ? settings.volumeProfile : null;
        }

        private static void RestoreDefaultVolumeProfile(
            VolumeProfile previous,
            UnityEngine.Object owner,
            string label,
            List<string> preserved,
            List<string> deliberateDefaults
        )
        {
            if (previous == null)
            {
                deliberateDefaults.Add(
                    $"{label}: no default volume profile was assigned before the repair; the installed URP default was kept"
                );
                return;
            }

            string previousPath = AssetDatabase.GetAssetPath(previous);
            if (string.IsNullOrEmpty(previousPath) || !previousPath.StartsWith("Assets/", StringComparison.Ordinal))
            {
                deliberateDefaults.Add(
                    $"{label}: previous default volume profile '{previousPath}' is not a project asset; " +
                    "the installed URP default was kept"
                );
                return;
            }

            bool found = EditorGraphicsSettings
                .TryGetRenderPipelineSettingsForPipeline<URPDefaultVolumeProfileSettings, UniversalRenderPipeline>(
                    out URPDefaultVolumeProfileSettings settings
                );
            if (!found || settings == null)
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} repaired {label} but could not read URPDefaultVolumeProfileSettings afterwards, so the " +
                    $"project default volume profile {previousPath} could not be restored. Restore the pre-repair copy " +
                    "and re-run once the installed URP version is understood."
                );
            }

            VolumeProfile current = settings.volumeProfile;
            if (ReferenceEquals(current, previous))
            {
                preserved.Add($"{label}: default volume profile already {previousPath}");
                return;
            }

            settings.volumeProfile = previous;
            EditorUtility.SetDirty(owner);
            AssetDatabase.SaveAssetIfDirty(owner);

            VolumeProfile verified = ReadDefaultVolumeProfile();
            if (!ReferenceEquals(verified, previous))
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} failed to restore the project default volume profile {previousPath} on {label}. " +
                    "Refusing to report a successful repair with a lost project-wide Volume default."
                );
            }

            string currentPath = current == null ? "<null>" : AssetDatabase.GetAssetPath(current);
            preserved.Add($"{label}: restored default volume profile {currentPath} -> {previousPath}");
        }

        // Reports, but never guesses at, project asset references that the installed
        // URP version did not carry across. Anything listed here is a deliberate
        // default the operator must review.
        private static void ReportProjectAssetReferenceLosses(
            Dictionary<string, UnityEngine.Object> previousReferences,
            UnityEngine.Object repaired,
            string label,
            List<string> preserved,
            List<string> deliberateDefaults
        )
        {
            Dictionary<string, UnityEngine.Object> currentReferences = CollectProjectAssetReferences(repaired);
            foreach (KeyValuePair<string, UnityEngine.Object> entry in previousReferences)
            {
                string previousPath = AssetDatabase.GetAssetPath(entry.Value);
                if (currentReferences.TryGetValue(entry.Key, out UnityEngine.Object current) &&
                    ReferenceEquals(current, entry.Value))
                {
                    preserved.Add($"{label}: project asset reference {entry.Key} -> {previousPath} survived the repair");
                    continue;
                }

                string currentPath = current == null ? "<absent>" : AssetDatabase.GetAssetPath(current);
                deliberateDefaults.Add(
                    $"{label}: project asset reference {entry.Key} was {previousPath} before the repair and is " +
                    $"{currentPath} after it; the installed URP version does not expose a public setter for it"
                );
            }
        }

        private static Dictionary<string, UnityEngine.Object> CollectProjectAssetReferences(UnityEngine.Object source)
        {
            var references = new Dictionary<string, UnityEngine.Object>(StringComparer.Ordinal);
            var sourceObject = new SerializedObject(source);
            SerializedProperty iterator = sourceObject.GetIterator();

            while (iterator.Next(true))
            {
                if (iterator.propertyType != SerializedPropertyType.ObjectReference)
                {
                    continue;
                }
                UnityEngine.Object value = iterator.objectReferenceValue;
                if (value == null)
                {
                    continue;
                }
                string path = AssetDatabase.GetAssetPath(value);
                if (string.IsNullOrEmpty(path) || !path.StartsWith("Assets/", StringComparison.Ordinal))
                {
                    continue;
                }
                string stableKey = StableProjectReferenceKey(sourceObject, iterator);
                if (!references.ContainsKey(stableKey))
                {
                    references.Add(stableKey, value);
                }
            }

            return references;
        }

        private static string StableProjectReferenceKey(
            SerializedObject owner,
            SerializedProperty property
        )
        {
            const string listPath = "m_Settings.m_SettingsList.m_List";
            const string elementPrefix = listPath + ".Array.data[";
            string path = property.propertyPath;
            if (!path.StartsWith(elementPrefix, StringComparison.Ordinal))
            {
                return path;
            }

            int indexEnd = path.IndexOf(']', elementPrefix.Length);
            if (indexEnd < 0 ||
                !int.TryParse(
                    path.Substring(elementPrefix.Length, indexEnd - elementPrefix.Length),
                    NumberStyles.Integer,
                    CultureInfo.InvariantCulture,
                    out int index
                ))
            {
                return path;
            }
            SerializedProperty list = owner.FindProperty(listPath);
            if (list == null || index < 0 || index >= list.arraySize)
            {
                return path;
            }
            SerializedProperty element = list.GetArrayElementAtIndex(index);
            string typeName = element.managedReferenceFullTypename;
            if (string.IsNullOrEmpty(typeName))
            {
                return path;
            }
            string relativePath = path.Substring(indexEnd + 1);
            return $"managed:{typeName}{relativePath}";
        }

        private static UrpAssetProbe[] ProbeAll()
        {
            var probes = new List<UrpAssetProbe>();
            var seenPaths = new HashSet<string>(StringComparer.Ordinal);

            RenderPipelineGlobalSettings globalSettings =
                EditorGraphicsSettings.GetRenderPipelineGlobalSettingsAsset<UniversalRenderPipeline>();
            if (globalSettings != null)
            {
                probes.Add(ProbeAsset(globalSettings, "globalSettings", GlobalSettingsVersionProperty, "graphicsSettingsGlobalSettingsMap"));
                seenPaths.Add(AssetDatabase.GetAssetPath(globalSettings));
            }

            RenderPipelineAsset defaultPipeline = GraphicsSettings.defaultRenderPipeline;
            if (defaultPipeline != null)
            {
                string path = AssetDatabase.GetAssetPath(defaultPipeline);
                if (seenPaths.Add(path))
                {
                    probes.Add(ProbeAsset(defaultPipeline, "renderPipelineAsset", RenderPipelineAssetVersionProperty, "graphicsSettingsDefaultRenderPipeline"));
                }
            }

            for (int index = 0; index < QualitySettings.count; index += 1)
            {
                RenderPipelineAsset levelPipeline = QualitySettings.GetRenderPipelineAssetAt(index);
                if (levelPipeline == null)
                {
                    continue;
                }
                string path = AssetDatabase.GetAssetPath(levelPipeline);
                string levelName = QualityLevelName(index);
                if (!seenPaths.Add(path))
                {
                    foreach (UrpAssetProbe existing in probes)
                    {
                        if (string.Equals(existing.assetPath, path, StringComparison.Ordinal))
                        {
                            existing.registeredBy = $"{existing.registeredBy}; qualityLevel[{index}]:{levelName}";
                        }
                    }
                    continue;
                }
                probes.Add(ProbeAsset(levelPipeline, "renderPipelineAsset", RenderPipelineAssetVersionProperty, $"qualityLevel[{index}]:{levelName}"));
            }

            return probes.ToArray();
        }

        private static UrpAssetProbe ProbeAsset(
            UnityEngine.Object asset,
            string role,
            string versionProperty,
            string registeredBy
        )
        {
            string path = AssetDatabase.GetAssetPath(asset);
            var probe = new UrpAssetProbe
            {
                role = role,
                assetPath = path,
                guid = AssetDatabase.AssetPathToGUID(path),
                typeName = asset.GetType().FullName,
                versionProperty = versionProperty,
                serializedVersion = ReadIntProperty(asset, versionProperty),
                expectedVersion = ProbeExpectedVersion(asset, versionProperty),
                registeredBy = registeredBy,
                missingManagedReferenceTypes = DescribeMissingManagedReferences(asset),
                rendererDataPaths = DescribeRendererData(asset)
            };
            probe.versionMatches =
                probe.serializedVersion >= 0 &&
                probe.expectedVersion >= 0 &&
                probe.serializedVersion == probe.expectedVersion;
            probe.compatible = probe.versionMatches && probe.missingManagedReferenceTypes.Length == 0;
            return probe;
        }

        // Discovers the version the INSTALLED URP expects, without hardcoding it and
        // without reading the internal k_LastVersion constant: a freshly constructed
        // instance initialises its version field to that constant.
        private static int ProbeExpectedVersion(UnityEngine.Object asset, string versionProperty)
        {
            ScriptableObject probeInstance = ScriptableObject.CreateInstance(asset.GetType());
            if (probeInstance == null)
            {
                return -1;
            }
            try
            {
                return ReadIntProperty(probeInstance, versionProperty);
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(probeInstance);
            }
        }

        private static int ReadIntProperty(UnityEngine.Object target, string propertyPath)
        {
            if (target == null)
            {
                return -1;
            }
            var serializedObject = new SerializedObject(target);
            SerializedProperty property = serializedObject.FindProperty(propertyPath);
            return property == null ? -1 : property.intValue;
        }

        private static string[] DescribeMissingManagedReferences(UnityEngine.Object asset)
        {
            if (!SerializationUtility.HasManagedReferencesWithMissingTypes(asset))
            {
                return new string[0];
            }

            ManagedReferenceMissingType[] missing = SerializationUtility.GetManagedReferencesWithMissingTypes(asset);
            var described = new string[missing.Length];
            for (int index = 0; index < missing.Length; index += 1)
            {
                described[index] =
                    $"{missing[index].namespaceName}.{missing[index].className} ({missing[index].assemblyName})";
            }
            return described;
        }

        private static string[] DescribeRendererData(UnityEngine.Object asset)
        {
            var pipelineAsset = asset as UniversalRenderPipelineAsset;
            if (pipelineAsset == null)
            {
                return new string[0];
            }

            ReadOnlySpan<ScriptableRendererData> rendererDataList = pipelineAsset.rendererDataList;
            var paths = new string[rendererDataList.Length];
            for (int index = 0; index < rendererDataList.Length; index += 1)
            {
                ScriptableRendererData rendererData = rendererDataList[index];
                paths[index] = rendererData == null ? "<null>" : AssetDatabase.GetAssetPath(rendererData);
            }
            return paths;
        }

        private static void AssertRendererDataPreserved(
            UniversalRenderPipelineAsset asset,
            string[] expectedPaths,
            int expectedDefaultIndex,
            string label
        )
        {
            string[] actualPaths = DescribeRendererData(asset);
            if (actualPaths.Length != expectedPaths.Length)
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} changed the renderer data slot count for {label}: " +
                    $"{expectedPaths.Length} -> {actualPaths.Length}."
                );
            }
            for (int index = 0; index < expectedPaths.Length; index += 1)
            {
                if (!string.Equals(expectedPaths[index], actualPaths[index], StringComparison.Ordinal))
                {
                    throw new InvalidOperationException(
                        $"{LogPrefix} changed renderer data slot {index} for {label}: " +
                        $"{expectedPaths[index]} -> {actualPaths[index]}."
                    );
                }
            }
            int actualDefaultIndex = ReadIntProperty(asset, "m_DefaultRendererIndex");
            if (actualDefaultIndex != expectedDefaultIndex)
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} changed the default renderer index for {label}: " +
                    $"{expectedDefaultIndex} -> {actualDefaultIndex}."
                );
            }
        }

        private static string QualityLevelName(int index)
        {
            string[] names = QualitySettings.names;
            return index >= 0 && index < names.Length ? names[index] : index.ToString(CultureInfo.InvariantCulture);
        }

        private static bool AllCompatible(UrpAssetProbe[] probes)
        {
            if (probes.Length == 0)
            {
                return false;
            }
            foreach (UrpAssetProbe probe in probes)
            {
                if (!probe.compatible)
                {
                    return false;
                }
            }
            return true;
        }

        private static bool RegistrationsChanged(UrpAssetProbe[] before, UrpAssetProbe[] after)
        {
            if (before.Length != after.Length)
            {
                return true;
            }
            for (int index = 0; index < before.Length; index += 1)
            {
                if (!string.Equals(before[index].assetPath, after[index].assetPath, StringComparison.Ordinal) ||
                    !string.Equals(before[index].guid, after[index].guid, StringComparison.Ordinal) ||
                    !string.Equals(before[index].registeredBy, after[index].registeredBy, StringComparison.Ordinal))
                {
                    return true;
                }
            }
            return false;
        }

        private static string Describe(UrpAssetProbe probe)
        {
            string missing = probe.missingManagedReferenceTypes.Length == 0
                ? "none"
                : string.Join(" | ", probe.missingManagedReferenceTypes);
            string renderers = probe.rendererDataPaths.Length == 0
                ? "none"
                : string.Join(" | ", probe.rendererDataPaths);
            return
                $"path={probe.assetPath}, guid={probe.guid}, type={probe.typeName}, role={probe.role}, " +
                $"registeredBy={probe.registeredBy}, {probe.versionProperty}={probe.serializedVersion}, " +
                $"expected={probe.expectedVersion}, versionMatches={probe.versionMatches}, " +
                $"missingSerializeReferenceTypes=[{missing}], rendererData=[{renderers}], " +
                $"compatible={probe.compatible}";
        }

        private static void AssertEditorVersionMatchesProject()
        {
            string projectEditorVersion = ReadProjectEditorVersion();
            if (string.IsNullOrEmpty(projectEditorVersion))
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} could not read m_EditorVersion from ProjectSettings/ProjectVersion.txt. " +
                    "Refusing to continue without knowing which editor this project is locked to."
                );
            }
            if (!string.Equals(projectEditorVersion, Application.unityVersion, StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} editor version mismatch: this project is locked to {projectEditorVersion} but the " +
                    $"running editor is {Application.unityVersion}. Opening or building this project with a different " +
                    "editor is what serializes render pipeline assets to an incompatible version. Reopen the project " +
                    $"with Unity {projectEditorVersion}."
                );
            }
        }

        private static string ReadProjectEditorVersion()
        {
            string path = Path.Combine(ProjectRoot(), "ProjectSettings", "ProjectVersion.txt");
            if (!File.Exists(path))
            {
                return null;
            }
            foreach (string line in File.ReadAllLines(path))
            {
                string trimmed = line.Trim();
                if (trimmed.StartsWith("m_EditorVersion:", StringComparison.Ordinal))
                {
                    return trimmed.Substring("m_EditorVersion:".Length).Trim();
                }
            }
            return null;
        }

        private static string ProjectRoot()
        {
            return Path.GetDirectoryName(Application.dataPath)?.Replace('\\', '/') ?? Application.dataPath;
        }

        // Logs/ is not imported by the Unity asset database and is covered by the
        // GR-BH-XR repository's [Ll]ogs/ ignore rule, so reports never become
        // project assets and never enter version control.
        private static string ReportDirectory()
        {
            string configured = CommandLineValue(ReportDirArgument, null);
            if (!string.IsNullOrWhiteSpace(configured))
            {
                return configured;
            }
            return Path.Combine(ProjectRoot(), "Logs", "GRBHXR", "urp_asset_repair");
        }

        private static void BackupAssetFile(string assetPath, string backupDirectory)
        {
            if (string.IsNullOrEmpty(assetPath))
            {
                throw new InvalidOperationException($"{LogPrefix} cannot back up an asset with an empty path.");
            }
            string absolute = Path.Combine(ProjectRoot(), assetPath);
            if (!File.Exists(absolute))
            {
                throw new FileNotFoundException(
                    $"{LogPrefix} cannot repair {assetPath} because its serialized file is missing.",
                    absolute
                );
            }
            string destination = Path.Combine(backupDirectory, Path.GetFileName(assetPath));
            File.Copy(absolute, destination, overwrite: true);
            string meta = absolute + ".meta";
            if (File.Exists(meta))
            {
                File.Copy(meta, destination + ".meta", overwrite: true);
            }
        }

        private static void RestoreBackups(UrpAssetProbe[] probes, string backupDirectory, List<string> actions)
        {
            foreach (UrpAssetProbe probe in probes)
            {
                if (probe.compatible)
                {
                    continue;
                }
                string source = Path.Combine(backupDirectory, Path.GetFileName(probe.assetPath));
                if (!File.Exists(source))
                {
                    throw new FileNotFoundException(
                        $"{LogPrefix} rollback copy is missing for {probe.assetPath}.",
                        source
                    );
                }
                string destination = Path.Combine(ProjectRoot(), probe.assetPath);
                File.Copy(source, destination, overwrite: true);

                string sourceMeta = source + ".meta";
                string destinationMeta = destination + ".meta";
                if (File.Exists(sourceMeta))
                {
                    File.Copy(sourceMeta, destinationMeta, overwrite: true);
                }
                AssetDatabase.ImportAsset(probe.assetPath, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
                actions.Add($"rollback restored {probe.assetPath} from {source}");
            }

            string globalSettingsPath = FindProbePath(probes, "globalSettings");
            if (!string.IsNullOrEmpty(globalSettingsPath))
            {
                RenderPipelineGlobalSettings globalSettings =
                    AssetDatabase.LoadAssetAtPath<RenderPipelineGlobalSettings>(globalSettingsPath);
                if (globalSettings != null)
                {
                    EditorGraphicsSettings.SetRenderPipelineGlobalSettingsAsset<UniversalRenderPipeline>(globalSettings);
                }
            }
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        }

        private static string FindProbePath(UrpAssetProbe[] probes, string role)
        {
            foreach (UrpAssetProbe probe in probes)
            {
                if (string.Equals(probe.role, role, StringComparison.Ordinal))
                {
                    return probe.assetPath;
                }
            }
            return null;
        }

        private static void PopulateEnvironment(UrpRepairReport report)
        {
            report.schema = ReportSchema;
            report.timestampUtc = DateTime.UtcNow.ToString("yyyyMMdd'T'HHmmss'Z'", CultureInfo.InvariantCulture);
            report.unityVersion = Application.unityVersion;
            report.projectEditorVersion = ReadProjectEditorVersion();
            report.editorVersionMatches = string.Equals(
                report.projectEditorVersion,
                report.unityVersion,
                StringComparison.Ordinal
            );
            report.projectPath = ProjectRoot();
            report.urpPackageVersion = ResolveUrpPackageVersion();
            report.defaultRenderPipelineAssetPath = GraphicsSettings.defaultRenderPipeline == null
                ? "<null>"
                : AssetDatabase.GetAssetPath(GraphicsSettings.defaultRenderPipeline);
            report.currentQualityLevel = QualitySettings.GetQualityLevel();

            var levels = new string[QualitySettings.count];
            for (int index = 0; index < QualitySettings.count; index += 1)
            {
                RenderPipelineAsset levelPipeline = QualitySettings.GetRenderPipelineAssetAt(index);
                string path = levelPipeline == null ? "<null>" : AssetDatabase.GetAssetPath(levelPipeline);
                levels[index] = $"[{index}] {QualityLevelName(index)} -> {path}";
            }
            report.qualityLevels = levels;
        }

        private static string ResolveUrpPackageVersion()
        {
            UnityEditor.PackageManager.PackageInfo package =
                UnityEditor.PackageManager.PackageInfo.FindForAssembly(typeof(UniversalRenderPipelineAsset).Assembly);
            return package == null ? "<unknown>" : $"{package.name}@{package.version}";
        }

        private static string WriteReport(UrpRepairReport report)
        {
            string directory = ReportDirectory();
            Directory.CreateDirectory(directory);
            string path = Path.Combine(directory, $"urp_asset_{report.mode}_{report.timestampUtc}.json");
            File.WriteAllText(path, JsonUtility.ToJson(report, prettyPrint: true));
            return path.Replace('\\', '/');
        }

        private static string CommandLineValue(string key, string fallback)
        {
            string[] args = Environment.GetCommandLineArgs();
            for (int index = 0; index < args.Length - 1; index += 1)
            {
                if (string.Equals(args[index], key, StringComparison.OrdinalIgnoreCase))
                {
                    return args[index + 1];
                }
            }
            return fallback;
        }

        private static int CommandLineIntValue(string key, int fallback)
        {
            string raw = CommandLineValue(key, null);
            if (string.IsNullOrEmpty(raw))
            {
                return fallback;
            }
            if (!int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out int value) || value < 0)
            {
                throw new InvalidOperationException(
                    $"{LogPrefix} expected a non-negative integer after {key}, got '{raw}'."
                );
            }
            return value;
        }

        [Serializable]
        private sealed class UrpAssetProbe
        {
            public string role;
            public string assetPath;
            public string guid;
            public string typeName;
            public string registeredBy;
            public string versionProperty;
            public int serializedVersion;
            public int expectedVersion;
            public bool versionMatches;
            public bool compatible;
            public string[] missingManagedReferenceTypes = new string[0];
            public string[] rendererDataPaths = new string[0];
        }

        [Serializable]
        private sealed class UrpRepairReport
        {
            public string schema;
            public string mode;
            public string timestampUtc;
            public string unityVersion;
            public string projectEditorVersion;
            public bool editorVersionMatches;
            public string projectPath;
            public string urpPackageVersion;
            public string defaultRenderPipelineAssetPath;
            public int currentQualityLevel;
            public string[] qualityLevels = new string[0];
            public string backupDirectory;
            public UrpAssetProbe[] before = new UrpAssetProbe[0];
            public UrpAssetProbe[] after = new UrpAssetProbe[0];
            public string[] actions = new string[0];
            public string[] preservedValues = new string[0];
            public string[] deliberateDefaults = new string[0];
            public bool rollbackPerformed;
            public string failure;
            public bool registrationsChanged;
            public bool compatibleAfter;
        }
    }
}
