using UnityEngine;

namespace GRBHXR
{
    [ExecuteAlways]
    public sealed class BlackHoleLensFloatingPanel : MonoBehaviour
    {
        [SerializeField] private Camera targetCamera;
        [SerializeField] private BlackHoleLensAnchorControls controls;
        [SerializeField] private BlackHoleXrHeadPoseDriver headPoseDriver;
        [SerializeField] private BlackHoleLensXrControllerControls xrControllerControls;
        [SerializeField] private BlackHoleLensRuntimeSettings runtimeSettings;
        // Horizontally centered on the gaze axis: a left-offset panel with an
        // upper-left text anchor pushed long status lines outside the HMD FOV.
        [SerializeField] private Vector3 cameraLocalOffset = new Vector3(0.0f, 0.28f, 1.55f);
        [SerializeField] private float textCharacterSize = 0.013f;
        [SerializeField] private Color textColor = new Color(0.82f, 0.94f, 1.0f, 1.0f);
        [SerializeField] private bool followCamera = true;
        [SerializeField] private bool visible;

        private TextMesh textMesh;

        public bool IsVisible => visible;

        private void Awake()
        {
            ResolveReferences();
            EnsureTextMesh();
        }

        private void OnEnable()
        {
            RefreshNow();
        }

        private void LateUpdate()
        {
            RefreshNow();
        }

        public void SetVisible(bool value)
        {
            visible = value;
            RefreshNow();
        }

        public void ToggleVisible()
        {
            SetVisible(!visible);
        }

        public void RefreshNow()
        {
            ResolveReferences();
            EnsureTextMesh();

            if (followCamera && targetCamera != null)
            {
                transform.position = targetCamera.transform.TransformPoint(cameraLocalOffset);
                transform.rotation = targetCamera.transform.rotation;
            }

            if (textMesh != null)
            {
                textMesh.gameObject.SetActive(visible);
                textMesh.characterSize = textCharacterSize;
                textMesh.color = textColor;
                textMesh.anchor = TextAnchor.UpperCenter;
                textMesh.alignment = TextAlignment.Left;
                textMesh.text = controls != null
                    ? controls.StatusText()
                    : "GR-BH-XR Lens Controls\nNo anchor controller bound.";
                if (headPoseDriver != null)
                {
                    Vector3 euler = headPoseDriver.LastHeadLocalRotation.eulerAngles;
                    textMesh.text +=
                        $"\nHead valid={headPoseDriver.PoseValid} rot=({euler.x:F0},{euler.y:F0},{euler.z:F0})";
                }
                if (xrControllerControls != null)
                {
                    textMesh.text += $"\n{xrControllerControls.StatusText()}";
                }
                if (runtimeSettings != null)
                {
                    textMesh.text += $"\n{runtimeSettings.StatusText()}";
                }
            }
        }

        private void ResolveReferences()
        {
            if (targetCamera == null)
            {
                targetCamera = Camera.main;
            }
            if (controls == null)
            {
                controls = FindAnyObjectByType<BlackHoleLensAnchorControls>();
            }
            if (headPoseDriver == null)
            {
                headPoseDriver = FindAnyObjectByType<BlackHoleXrHeadPoseDriver>();
            }
            if (xrControllerControls == null)
            {
                xrControllerControls = FindAnyObjectByType<BlackHoleLensXrControllerControls>();
            }
            if (runtimeSettings == null)
            {
                runtimeSettings = FindAnyObjectByType<BlackHoleLensRuntimeSettings>();
            }
        }

        private void EnsureTextMesh()
        {
            if (textMesh != null)
            {
                return;
            }

            var textObject = transform.Find("StatusText");
            if (textObject == null)
            {
                var child = new GameObject("StatusText");
                child.transform.SetParent(transform, worldPositionStays: false);
                child.transform.localPosition = Vector3.zero;
                child.transform.localRotation = Quaternion.identity;
                child.transform.localScale = Vector3.one;
                textObject = child.transform;
            }

            textMesh = textObject.GetComponent<TextMesh>();
            if (textMesh == null)
            {
                textMesh = textObject.gameObject.AddComponent<TextMesh>();
            }
            textMesh.anchor = TextAnchor.UpperCenter;
            textMesh.alignment = TextAlignment.Left;
            textMesh.fontSize = 64;
        }
    }
}
