using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace GRBHXR
{
    [ExecuteAlways]
    public sealed class BlackHoleLensSettingsPanel : MonoBehaviour
    {
        [SerializeField] private Camera targetCamera;
        [SerializeField] private BlackHoleLensAnchorControls controls;
        [SerializeField] private BlackHoleLensRuntimeSettings runtimeSettings;
        [SerializeField] private Vector3 cameraLocalOffset = new Vector3(0.0f, -0.08f, 1.65f);
        [SerializeField] private Vector2 panelSize = new Vector2(0.72f, 0.54f);
        [SerializeField] private float pixelsPerMeter = 900.0f;
        [SerializeField] private float dragDistance = 1.65f;
        [SerializeField] private bool visible;

        private readonly List<Action> actions = new List<Action>();
        private readonly List<Text> buttonLabels = new List<Text>();
        private readonly List<Image> buttonImages = new List<Image>();
        private Canvas canvas;
        private RectTransform root;
        private Text titleText;
        private Text statusText;
        private Text footerText;
        private int selectedIndex;
        private float nextNavigateTime;

        public bool IsVisible => visible;

        private void Awake()
        {
            ResolveReferences();
            EnsureUi();
            Refresh();
        }

        private void OnEnable()
        {
            ResolveReferences();
            EnsureUi();
            Refresh();
        }

        private void LateUpdate()
        {
            if (visible)
            {
                Refresh();
            }
        }

        public void ToggleVisible()
        {
            SetVisible(!visible, placeInFrontOfCamera: !visible);
        }

        public void SetVisible(bool value, bool placeInFrontOfCamera = false)
        {
            visible = value;
            if (visible && placeInFrontOfCamera)
            {
                PlaceInFrontOfCamera();
            }
            Refresh();
        }

        public void Navigate(Vector2 axis)
        {
            if (!visible || actions.Count == 0 || Time.unscaledTime < nextNavigateTime)
            {
                return;
            }

            int delta = 0;
            if (Mathf.Abs(axis.y) > 0.55f)
            {
                delta = axis.y > 0.0f ? -1 : 1;
            }
            else if (Mathf.Abs(axis.x) > 0.65f)
            {
                delta = axis.x > 0.0f ? 1 : -1;
            }
            if (delta == 0)
            {
                return;
            }

            selectedIndex = Mathf.Clamp(selectedIndex + delta, 0, actions.Count - 1);
            nextNavigateTime = Time.unscaledTime + 0.22f;
            Refresh();
        }

        public void ActivateSelected()
        {
            if (!visible || selectedIndex < 0 || selectedIndex >= actions.Count)
            {
                return;
            }
            actions[selectedIndex]?.Invoke();
            Refresh();
        }

        public void DragToRay(Vector3 origin, Vector3 direction)
        {
            if (!visible || direction.sqrMagnitude < 1.0e-6f)
            {
                return;
            }
            Vector3 rayDirection = direction.normalized;
            transform.position = origin + rayDirection * Mathf.Max(dragDistance, 0.4f);
            FaceCamera();
        }

        public void PlaceInFrontOfCamera()
        {
            ResolveReferences();
            if (targetCamera == null)
            {
                return;
            }
            transform.position = targetCamera.transform.TransformPoint(cameraLocalOffset);
            dragDistance = Vector3.Distance(transform.position, targetCamera.transform.position);
            FaceCamera();
        }

        private void FaceCamera()
        {
            ResolveReferences();
            if (targetCamera == null)
            {
                return;
            }
            transform.rotation = Quaternion.LookRotation(
                transform.position - targetCamera.transform.position,
                targetCamera.transform.up
            );
        }

        private void Refresh()
        {
            EnsureUi();
            if (canvas != null)
            {
                canvas.gameObject.SetActive(visible);
            }
            if (!visible)
            {
                return;
            }

            if (titleText != null)
            {
                titleText.text = "GR-BH-XR Settings";
            }
            if (statusText != null)
            {
                string pose = controls != null
                    ? $"Aim yaw {controls.YawDegrees:F1}  pitch {controls.PitchDegrees:F1}  roll {controls.RollDegrees:F1}"
                    : "No lens anchor bound";
                string disk = runtimeSettings != null
                    ? runtimeSettings.StatusText().Replace("\n", "  ")
                    : "No disk settings bound";
                statusText.text =
                    $"{pose}\n{disk}\n" +
                    "Tier 0 playback: spin / inclination / r_obs need GPU regenerate.";
            }
            if (footerText != null)
            {
                footerText.text = "Right stick selects    A/trigger activates    B closes";
            }

            for (int i = 0; i < buttonImages.Count; i += 1)
            {
                bool selected = i == selectedIndex;
                buttonImages[i].color = selected
                    ? new Color(0.18f, 0.47f, 0.82f, 0.92f)
                    : new Color(0.05f, 0.08f, 0.12f, 0.82f);
                buttonLabels[i].color = selected ? Color.white : new Color(0.78f, 0.88f, 0.95f, 1.0f);
            }
        }

        private void EnsureUi()
        {
            if (canvas != null)
            {
                return;
            }

            var canvasObject = new GameObject("SettingsCanvas");
            canvasObject.transform.SetParent(transform, worldPositionStays: false);
            canvasObject.transform.localPosition = Vector3.zero;
            canvasObject.transform.localRotation = Quaternion.identity;
            canvasObject.transform.localScale = Vector3.one / pixelsPerMeter;
            canvas = canvasObject.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;
            canvas.sortingOrder = 20;
            canvasObject.AddComponent<GraphicRaycaster>();

            root = canvasObject.GetComponent<RectTransform>();
            root.sizeDelta = panelSize * pixelsPerMeter;

            var background = canvasObject.AddComponent<Image>();
            background.color = new Color(0.015f, 0.02f, 0.03f, 0.90f);

            titleText = CreateText("Title", root, "GR-BH-XR Settings", 30, TextAnchor.MiddleLeft);
            SetRect(titleText.rectTransform, new Vector2(24, -28), new Vector2(root.sizeDelta.x - 48, 42), new Vector2(0, 1));

            statusText = CreateText("Status", root, "", 16, TextAnchor.UpperLeft);
            SetRect(statusText.rectTransform, new Vector2(24, -76), new Vector2(root.sizeDelta.x - 48, 74), new Vector2(0, 1));

            actions.Clear();
            buttonLabels.Clear();
            buttonImages.Clear();
            float y = -166.0f;
            AddButton("Aim at View", y, () => controls?.ResetPose());
            AddButton("Disk Visual On/Off", y - 48.0f, () => runtimeSettings?.ToggleDiskVisualMode());
            AddButton("Disk Audit Off / m0 / m1", y - 96.0f, () => runtimeSettings?.CycleDiskAuditMode());
            AddTwoButtonRow("Opacity -", "Opacity +", y - 144.0f,
                () => runtimeSettings?.AddDiskOpacity(-0.08f),
                () => runtimeSettings?.AddDiskOpacity(0.08f));
            AddTwoButtonRow("Brightness -", "Brightness +", y - 192.0f,
                () => runtimeSettings?.AddDiskBrightness(-0.15f),
                () => runtimeSettings?.AddDiskBrightness(0.15f));
            AddTwoButtonRow("g Power -", "g Power +", y - 240.0f,
                () => runtimeSettings?.AddDiskGPower(-0.25f),
                () => runtimeSettings?.AddDiskGPower(0.25f));
            AddButton("Request closer r_obs map", y - 288.0f, () => controls?.RequestObserverRadiusChange(50.0f));
            AddButton("Request farther r_obs map", y - 336.0f, () => controls?.RequestObserverRadiusChange(200.0f));

            footerText = CreateText("Footer", root, "", 14, TextAnchor.MiddleCenter);
            SetRect(footerText.rectTransform, new Vector2(24, 20), new Vector2(root.sizeDelta.x - 48, 30), new Vector2(0, 0));
            canvasObject.SetActive(visible);
        }

        private void AddButton(string label, float y, Action action)
        {
            AddButton(label, new Vector2(24.0f, y), new Vector2(root.sizeDelta.x - 48.0f, 36.0f), action);
        }

        private void AddTwoButtonRow(string leftLabel, string rightLabel, float y, Action leftAction, Action rightAction)
        {
            float width = (root.sizeDelta.x - 58.0f) * 0.5f;
            AddButton(leftLabel, new Vector2(24.0f, y), new Vector2(width, 36.0f), leftAction);
            AddButton(rightLabel, new Vector2(34.0f + width, y), new Vector2(width, 36.0f), rightAction);
        }

        private void AddButton(string label, Vector2 anchoredPosition, Vector2 size, Action action)
        {
            var buttonObject = new GameObject(label);
            buttonObject.transform.SetParent(root, worldPositionStays: false);
            var rect = buttonObject.AddComponent<RectTransform>();
            SetRect(rect, anchoredPosition, size, new Vector2(0, 1));
            var image = buttonObject.AddComponent<Image>();
            var button = buttonObject.AddComponent<Button>();
            button.targetGraphic = image;
            button.onClick.AddListener(() => action?.Invoke());

            var text = CreateText("Label", rect, label, 16, TextAnchor.MiddleCenter);
            SetRect(text.rectTransform, Vector2.zero, size, new Vector2(0.5f, 0.5f));
            actions.Add(action);
            buttonLabels.Add(text);
            buttonImages.Add(image);
        }

        private static Text CreateText(string name, Transform parent, string text, int size, TextAnchor anchor)
        {
            var textObject = new GameObject(name);
            textObject.transform.SetParent(parent, worldPositionStays: false);
            var label = textObject.AddComponent<Text>();
            label.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            label.text = text;
            label.fontSize = size;
            label.alignment = anchor;
            label.color = new Color(0.78f, 0.88f, 0.95f, 1.0f);
            return label;
        }

        private static void SetRect(RectTransform rect, Vector2 anchoredPosition, Vector2 size, Vector2 anchor)
        {
            rect.anchorMin = anchor;
            rect.anchorMax = anchor;
            rect.pivot = anchor;
            rect.anchoredPosition = anchoredPosition;
            rect.sizeDelta = size;
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
            if (runtimeSettings == null)
            {
                runtimeSettings = FindAnyObjectByType<BlackHoleLensRuntimeSettings>();
            }
        }
    }
}
