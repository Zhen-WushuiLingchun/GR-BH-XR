using UnityEngine;

namespace GRBHXR
{
    [ExecuteAlways]
    public sealed class BlackHoleLensRuntimeSettings : MonoBehaviour
    {
        [SerializeField] private Material targetMaterial;
        [SerializeField] private Renderer targetRenderer;
        [SerializeField] private bool diskVisualMode;
        [SerializeField] private int diskAuditMode;
        [SerializeField] private float diskOpacity = 0.85f;
        [SerializeField] private float diskBrightness = 1.0f;
        [SerializeField] private float diskGPower = 3.0f;
        [SerializeField] private float diskSecondaryScale = 0.32f;

        public bool DiskVisualMode => diskVisualMode;
        public int DiskAuditMode => diskAuditMode;
        public float DiskOpacity => diskOpacity;
        public float DiskBrightness => diskBrightness;
        public float DiskGPower => diskGPower;

        private void Awake()
        {
            ResolveMaterial();
            Apply();
        }

        private void OnEnable()
        {
            ResolveMaterial();
            Apply();
        }

        private void OnValidate()
        {
            Apply();
        }

        public void ToggleDiskVisualMode()
        {
            SetDiskVisualMode(!diskVisualMode);
        }

        public void SetDiskVisualMode(bool enabled)
        {
            diskVisualMode = enabled;
            if (enabled)
            {
                diskAuditMode = 0;
            }
            Apply();
        }

        public void CycleDiskAuditMode()
        {
            diskAuditMode = (diskAuditMode + 1) % 3;
            if (diskAuditMode != 0)
            {
                diskVisualMode = false;
            }
            Apply();
        }

        public void AddDiskOpacity(float delta)
        {
            diskOpacity = Mathf.Clamp01(diskOpacity + delta);
            Apply();
        }

        public void AddDiskBrightness(float delta)
        {
            diskBrightness = Mathf.Clamp(diskBrightness + delta, 0.0f, 4.0f);
            Apply();
        }

        public void AddDiskGPower(float delta)
        {
            diskGPower = Mathf.Clamp(diskGPower + delta, 0.0f, 6.0f);
            Apply();
        }

        public string StatusText()
        {
            string diskMode = diskVisualMode ? "visual" : "off";
            if (diskAuditMode == 1)
            {
                diskMode = "audit m0";
            }
            else if (diskAuditMode == 2)
            {
                diskMode = "audit m1";
            }
            return
                $"Disk {diskMode}  opacity {diskOpacity:F2}\n" +
                $"g^{diskGPower:F1}  bright {diskBrightness:F2}\n" +
                "X: disk visual  Y: disk audit";
        }

        public void Apply()
        {
            var material = ResolveMaterial();
            if (material == null)
            {
                return;
            }
            diskAuditMode = Mathf.Clamp(diskAuditMode, 0, 2);
            diskOpacity = Mathf.Clamp01(diskOpacity);
            diskBrightness = Mathf.Clamp(diskBrightness, 0.0f, 4.0f);
            diskGPower = Mathf.Clamp(diskGPower, 0.0f, 6.0f);
            diskSecondaryScale = Mathf.Clamp01(diskSecondaryScale);

            material.SetFloat("_DiskVisualMode", diskVisualMode ? 1.0f : 0.0f);
            material.SetFloat("_DiskAuditMode", diskAuditMode);
            material.SetFloat("_DiskOpacity", diskOpacity);
            material.SetFloat("_DiskBrightness", diskBrightness);
            material.SetFloat("_DiskGPower", diskGPower);
            material.SetFloat("_DiskSecondaryScale", diskSecondaryScale);
        }

        private Material ResolveMaterial()
        {
            if (targetMaterial != null)
            {
                return targetMaterial;
            }
            if (targetRenderer == null)
            {
                targetRenderer = GetComponent<Renderer>();
            }
            if (targetRenderer != null)
            {
                targetMaterial = targetRenderer.sharedMaterial;
            }
            return targetMaterial;
        }
    }
}
