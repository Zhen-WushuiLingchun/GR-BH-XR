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
        [SerializeField] private bool diskHotSpotEnabled;
        [SerializeField] private bool diskHotSpotAnimate;
        [SerializeField] private float diskHotSpotRadius = 8.0f;
        [SerializeField] private float diskHotSpotPhase;
        [SerializeField] private float diskHotSpotSigmaR = 1.0f;
        [SerializeField] private float diskHotSpotSigmaPhi = 0.18f;
        [SerializeField] private float diskHotSpotBrightness = 2.0f;
        [SerializeField] private float diskSpin = 0.9f;
        [SerializeField] private float diskInnerRadius = 2.32f;
        [SerializeField] private float diskOuterRadius = 30.0f;

        public bool DiskVisualMode => diskVisualMode;
        public int DiskAuditMode => diskAuditMode;
        public float DiskOpacity => diskOpacity;
        public float DiskBrightness => diskBrightness;
        public float DiskGPower => diskGPower;
        public bool DiskHotSpotEnabled => diskHotSpotEnabled;
        public bool DiskHotSpotAnimate => diskHotSpotAnimate;
        public float DiskHotSpotRadius => diskHotSpotRadius;
        public float DiskHotSpotPhase => diskHotSpotPhase;

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

        public void ToggleDiskHotSpot()
        {
            diskHotSpotEnabled = !diskHotSpotEnabled;
            if (diskHotSpotEnabled)
            {
                diskVisualMode = true;
                diskAuditMode = 0;
            }
            Apply();
        }

        public void ToggleDiskHotSpotAnimation()
        {
            diskHotSpotAnimate = !diskHotSpotAnimate;
            Apply();
        }

        public void AddDiskHotSpotRadius(float delta)
        {
            diskHotSpotRadius = Mathf.Clamp(
                diskHotSpotRadius + delta,
                diskInnerRadius + Mathf.Max(diskHotSpotSigmaR, 0.05f),
                diskOuterRadius - Mathf.Max(diskHotSpotSigmaR, 0.05f)
            );
            Apply();
        }

        public void AddDiskHotSpotPhase(float delta)
        {
            diskHotSpotPhase = NormalizeAngle(diskHotSpotPhase + delta);
            Apply();
        }

        public void AddDiskHotSpotWidth(float delta)
        {
            diskHotSpotSigmaR = Mathf.Clamp(diskHotSpotSigmaR + delta, 0.1f, 6.0f);
            diskHotSpotSigmaPhi = Mathf.Clamp(diskHotSpotSigmaPhi + 0.08f * delta, 0.03f, 1.2f);
            AddDiskHotSpotRadius(0.0f);
        }

        public void AddDiskHotSpotBrightness(float delta)
        {
            diskHotSpotBrightness = Mathf.Clamp(diskHotSpotBrightness + delta, 0.0f, 8.0f);
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
                $"Hotspot {(diskHotSpotEnabled ? "on" : "off")} r {diskHotSpotRadius:F1} phi {diskHotSpotPhase:F2}\n" +
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
            diskInnerRadius = Mathf.Max(0.01f, diskInnerRadius);
            diskOuterRadius = Mathf.Max(diskInnerRadius + 0.1f, diskOuterRadius);
            diskHotSpotSigmaR = Mathf.Clamp(diskHotSpotSigmaR, 0.1f, 6.0f);
            diskHotSpotSigmaPhi = Mathf.Clamp(diskHotSpotSigmaPhi, 0.03f, 1.2f);
            diskHotSpotBrightness = Mathf.Clamp(diskHotSpotBrightness, 0.0f, 8.0f);
            diskHotSpotRadius = Mathf.Clamp(
                diskHotSpotRadius,
                diskInnerRadius + diskHotSpotSigmaR,
                diskOuterRadius - diskHotSpotSigmaR
            );
            diskHotSpotPhase = NormalizeAngle(diskHotSpotPhase);

            material.SetFloat("_DiskVisualMode", diskVisualMode ? 1.0f : 0.0f);
            material.SetFloat("_DiskAuditMode", diskAuditMode);
            material.SetFloat("_DiskOpacity", diskOpacity);
            material.SetFloat("_DiskBrightness", diskBrightness);
            material.SetFloat("_DiskGPower", diskGPower);
            material.SetFloat("_DiskSecondaryScale", diskSecondaryScale);
            material.SetFloat("_DiskHotSpotEnabled", diskHotSpotEnabled ? 1.0f : 0.0f);
            material.SetFloat("_DiskHotSpotAnimate", diskHotSpotAnimate ? 1.0f : 0.0f);
            material.SetFloat("_DiskHotSpotRadius", diskHotSpotRadius);
            material.SetFloat("_DiskHotSpotPhase", diskHotSpotPhase);
            material.SetFloat("_DiskHotSpotSigmaR", diskHotSpotSigmaR);
            material.SetFloat("_DiskHotSpotSigmaPhi", diskHotSpotSigmaPhi);
            material.SetFloat("_DiskHotSpotBrightness", diskHotSpotBrightness);
            material.SetFloat("_DiskHotSpotOmega", KeplerianOmega(diskHotSpotRadius));
        }

        private float KeplerianOmega(float radius)
        {
            return 1.0f / (Mathf.Pow(Mathf.Max(radius, 1.0e-3f), 1.5f) + diskSpin);
        }

        private static float NormalizeAngle(float angle)
        {
            while (angle > Mathf.PI)
            {
                angle -= 2.0f * Mathf.PI;
            }
            while (angle <= -Mathf.PI)
            {
                angle += 2.0f * Mathf.PI;
            }
            return angle;
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
