using UnityEngine;

namespace GRBHXR
{
    [ExecuteAlways]
    public sealed class BlackHoleLensFloatingPanel : MonoBehaviour
    {
        [SerializeField] private Camera targetCamera;
        [SerializeField] private BlackHoleLensAnchorControls controls;
        [SerializeField] private Vector3 cameraLocalOffset = new Vector3(-0.42f, 0.28f, 1.25f);
        [SerializeField] private float textCharacterSize = 0.035f;
        [SerializeField] private Color textColor = new Color(0.82f, 0.94f, 1.0f, 1.0f);
        [SerializeField] private bool followCamera = true;
        [SerializeField] private bool visible = true;

        private TextMesh textMesh;

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
                textMesh.text = controls != null
                    ? controls.StatusText()
                    : "GR-BH-XR Lens Controls\nNo anchor controller bound.";
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
            textMesh.anchor = TextAnchor.UpperLeft;
            textMesh.alignment = TextAlignment.Left;
            textMesh.fontSize = 64;
        }
    }
}
