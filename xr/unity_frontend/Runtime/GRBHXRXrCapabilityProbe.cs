using System;
using System.Collections;
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEngine.XR.OpenXR;
using UnityEngine.XR.Management;

namespace GRBHXR
{
    /// <summary>
    /// MR capability probe: enumerates what the ACTIVE OpenXR runtime (Meta
    /// Link on PCVR) actually exposes to this app - runtime identity, the
    /// full extension list (passthrough / camera / depth / scene / spatial
    /// highlighted), and the Windows camera devices visible to Unity. The
    /// result is written to persistentDataPath/xr_capability_probe.json so
    /// the MR integration path is chosen from measured surface, not from
    /// documentation belief.
    /// </summary>
    public sealed class GRBHXRXrCapabilityProbe : MonoBehaviour
    {
        private static readonly string[] MrKeywords =
        {
            "passthrough", "camera", "depth", "scene", "spatial",
            "mesh", "plane", "anchor", "environment",
        };

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Bootstrap()
        {
            if (!Application.isPlaying)
            {
                return;
            }
            var host = new GameObject("GRBHXRXrCapabilityProbe")
            {
                hideFlags = HideFlags.DontSave,
            };
            DontDestroyOnLoad(host);
            host.AddComponent<GRBHXRXrCapabilityProbe>();
        }

        private IEnumerator Start()
        {
            // XR initialization is asynchronous; sample a few times so the
            // probe captures the post-init state even on slow Link startup.
            float[] delays = { 3.0f, 7.0f, 15.0f };
            foreach (float delay in delays)
            {
                yield return new WaitForSeconds(delay);
                try
                {
                    WriteProbe();
                }
                catch (Exception exception)
                {
                    Debug.LogWarning($"GR-BH-XR capability probe failed: {exception.Message}");
                }
            }
        }

        private void WriteProbe()
        {
            string loaderName = "none";
            var settings = XRGeneralSettings.Instance;
            if (settings != null && settings.Manager != null && settings.Manager.activeLoader != null)
            {
                loaderName = settings.Manager.activeLoader.name;
            }

            string[] available = OpenXRRuntime.GetAvailableExtensions() ?? new string[0];
            string[] enabled = OpenXRRuntime.GetEnabledExtensions() ?? new string[0];
            string[] mrRelevant = available
                .Where(ext => MrKeywords.Any(key => ext.ToLowerInvariant().Contains(key)))
                .ToArray();
            WebCamDevice[] cameras = WebCamTexture.devices;

            // Available vs enabled is the decisive discriminator for Task 10
            // and was previously written to the file but never evaluated, so
            // reading it meant retrieving the artifact off the device.
            string cameraExtensionState = BlackHoleMrPassthrough.CameraExtensionStateText();
            bool mrukTypePresent = BlackHoleMrPassthrough.ProbeOfficialCameraBackend(out string mrukReason);

            var json = new StringBuilder();
            json.Append("{\n");
            json.Append($"  \"probeTimeUtc\": \"{Esc(DateTime.UtcNow.ToString("O"))}\",\n");
            json.Append($"  \"xrLoader\": \"{Esc(loaderName)}\",\n");
            json.Append($"  \"openXrRuntime\": \"{Esc(OpenXRRuntime.name)}\",\n");
            json.Append($"  \"openXrRuntimeVersion\": \"{Esc(OpenXRRuntime.version)}\",\n");
            json.Append($"  \"openXrApiVersion\": \"{Esc(OpenXRRuntime.apiVersion)}\",\n");
            json.Append($"  \"openXrPluginVersion\": \"{Esc(OpenXRRuntime.pluginVersion)}\",\n");
            json.Append($"  \"cameraExtension\": \"{Esc(BlackHoleMrPassthrough.CameraExtensionName)}\",\n");
            json.Append($"  \"cameraExtensionState\": \"{Esc(cameraExtensionState)}\",\n");
            json.Append($"  \"cameraExtensionEnabled\": {(cameraExtensionState == "enabled" ? "true" : "false")},\n");
            json.Append($"  \"cameraExtensionAvailable\": {(cameraExtensionState == "enabled" || cameraExtensionState == "available" ? "true" : "false")},\n");
            json.Append($"  \"mrukTypePresent\": {(mrukTypePresent ? "true" : "false")},\n");
            json.Append($"  \"mrukTypeReason\": \"{Esc(mrukReason)}\",\n");
            json.Append($"  \"mrukTypeResolvedVia\": \"{Esc(BlackHoleMrukCameraBridge.ResolvedVia)}\",\n");
            json.Append("  \"mrRelevantExtensions\": [\n    ");
            json.Append(string.Join(",\n    ", mrRelevant.Select(ext => $"\"{Esc(ext)}\"")));
            json.Append("\n  ],\n");
            json.Append("  \"enabledExtensions\": [\n    ");
            json.Append(string.Join(",\n    ", enabled.Select(ext => $"\"{Esc(ext)}\"")));
            json.Append("\n  ],\n");
            json.Append("  \"cameraDevices\": [\n    ");
            json.Append(string.Join(
                ",\n    ",
                cameras.Select(cam => $"{{\"name\": \"{Esc(cam.name)}\", \"frontFacing\": {(cam.isFrontFacing ? "true" : "false")}}}")
            ));
            json.Append("\n  ],\n");
            json.Append("  \"availableExtensions\": [\n    ");
            json.Append(string.Join(",\n    ", available.Select(ext => $"\"{Esc(ext)}\"")));
            json.Append("\n  ]\n");
            json.Append("}\n");

            string path = System.IO.Path.Combine(Application.persistentDataPath, "xr_capability_probe.json");
            System.IO.File.WriteAllText(path, json.ToString());
            Debug.Log(
                $"GR-BH-XR capability probe: loader={loaderName}, runtime={OpenXRRuntime.name} {OpenXRRuntime.version}, " +
                $"extensions={available.Length} (MR-relevant {mrRelevant.Length}), cameras={cameras.Length}, " +
                $"cameraExt={cameraExtensionState}, mruk={(mrukTypePresent ? "present" : "absent")} ({mrukReason}) -> {path}"
            );
        }

        /// <summary>
        /// Minimal JSON string escaping. The probe builds its document by
        /// concatenation, and several interpolated values are outside this
        /// project's control - DirectShow camera friendly names in particular
        /// routinely contain quotes, backslashes and non-ASCII. One such
        /// character silently corrupted the artifact the device gate depends
        /// on.
        /// </summary>
        private static string Esc(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return string.Empty;
            }
            var sb = new StringBuilder(value.Length + 8);
            foreach (char c in value)
            {
                switch (c)
                {
                    case '\\': sb.Append("\\\\"); break;
                    case '"': sb.Append("\\\""); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    case '\b': sb.Append("\\b"); break;
                    case '\f': sb.Append("\\f"); break;
                    default:
                        if (c < 0x20)
                        {
                            sb.Append("\\u").Append(((int)c).ToString("x4"));
                        }
                        else
                        {
                            sb.Append(c);
                        }
                        break;
                }
            }
            return sb.ToString();
        }
    }
}
