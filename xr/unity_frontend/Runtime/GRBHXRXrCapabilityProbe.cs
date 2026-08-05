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

            var json = new StringBuilder();
            json.Append("{\n");
            json.Append($"  \"probeTimeUtc\": \"{DateTime.UtcNow:O}\",\n");
            json.Append($"  \"xrLoader\": \"{loaderName}\",\n");
            json.Append($"  \"openXrRuntime\": \"{OpenXRRuntime.name}\",\n");
            json.Append($"  \"openXrRuntimeVersion\": \"{OpenXRRuntime.version}\",\n");
            json.Append($"  \"openXrApiVersion\": \"{OpenXRRuntime.apiVersion}\",\n");
            json.Append($"  \"openXrPluginVersion\": \"{OpenXRRuntime.pluginVersion}\",\n");
            json.Append("  \"mrRelevantExtensions\": [\n    ");
            json.Append(string.Join(",\n    ", mrRelevant.Select(ext => $"\"{ext}\"")));
            json.Append("\n  ],\n");
            json.Append("  \"enabledExtensions\": [\n    ");
            json.Append(string.Join(",\n    ", enabled.Select(ext => $"\"{ext}\"")));
            json.Append("\n  ],\n");
            json.Append("  \"cameraDevices\": [\n    ");
            json.Append(string.Join(
                ",\n    ",
                cameras.Select(cam => $"{{\"name\": \"{cam.name}\", \"frontFacing\": {(cam.isFrontFacing ? "true" : "false")}}}")
            ));
            json.Append("\n  ],\n");
            json.Append("  \"availableExtensions\": [\n    ");
            json.Append(string.Join(",\n    ", available.Select(ext => $"\"{ext}\"")));
            json.Append("\n  ]\n");
            json.Append("}\n");

            string path = System.IO.Path.Combine(Application.persistentDataPath, "xr_capability_probe.json");
            System.IO.File.WriteAllText(path, json.ToString());
            Debug.Log(
                $"GR-BH-XR capability probe: loader={loaderName}, runtime={OpenXRRuntime.name} {OpenXRRuntime.version}, " +
                $"extensions={available.Length} (MR-relevant {mrRelevant.Length}), cameras={cameras.Length} -> {path}"
            );
        }
    }
}
