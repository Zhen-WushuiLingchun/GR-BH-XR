using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace GRBHXR
{
    [ExecuteAlways]
    public sealed class BlackHoleLensSettingsPanel : MonoBehaviour
    {
        // Panel palette: deep-space navy with a single cyan accent.
        private static readonly Color PanelBackground = new Color(0.030f, 0.050f, 0.082f, 0.965f);
        private static readonly Color HeaderStrip = new Color(0.075f, 0.125f, 0.195f, 1.0f);
        private static readonly Color ButtonNormal = new Color(0.095f, 0.140f, 0.205f, 0.92f);
        private static readonly Color ButtonSelected = new Color(0.145f, 0.475f, 0.820f, 0.97f);
        private static readonly Color LabelNormal = new Color(0.780f, 0.860f, 0.930f, 1.0f);
        private static readonly Color LabelSelected = Color.white;
        private static readonly Color SectionColor = new Color(0.470f, 0.690f, 0.920f, 1.0f);
        private static readonly Color StatusColor = new Color(0.640f, 0.730f, 0.810f, 1.0f);
        private static readonly Color FooterColor = new Color(0.470f, 0.540f, 0.620f, 1.0f);

        [SerializeField] private Camera targetCamera;
        [SerializeField] private BlackHoleLensAnchorControls controls;
        [SerializeField] private BlackHoleLensRuntimeSettings runtimeSettings;
        [SerializeField] private BlackHoleObserverRigControls observerRigControls;
        [SerializeField] private Vector3 cameraLocalOffset = new Vector3(0.0f, -0.05f, 1.65f);
        [SerializeField] private Vector2 panelSize = new Vector2(0.82f, 1.14f);
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
        private float layoutCursorY;
        private static Sprite roundedSprite;

        public bool IsVisible => visible;

        private void Awake()
        {
            if (Application.isPlaying)
            {
                // The scene may have been saved with the panel open; an XR
                // session must always start closed and open through B.
                visible = false;
            }
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

        private void OnDestroy()
        {
            // The generated canvas is HideFlags.DontSave, so scene teardown
            // does not destroy it implicitly.
            if (canvas != null)
            {
                DestroyGameObject(canvas.gameObject);
                canvas = null;
            }
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
            if (visible)
            {
                Close();
            }
            else
            {
                Open();
            }
        }

        public void Open()
        {
            selectedIndex = actions.Count > 1 ? 1 : 0;
            SetVisible(true, placeInFrontOfCamera: true);
        }

        public void Close()
        {
            SetVisible(false);
        }

        public void SetVisible(bool value, bool placeInFrontOfCamera = false)
        {
            bool changed = visible != value;
            visible = value;
            if (visible && placeInFrontOfCamera)
            {
                PlaceInFrontOfCamera();
            }
            Refresh();
            if (changed && Application.isPlaying)
            {
                Debug.Log($"GR-BH-XR settings panel visible={visible}.");
            }
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

            selectedIndex = (selectedIndex + delta + actions.Count) % actions.Count;
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
                titleText.text = "GR-BH-XR  ·  Kerr Roam";
            }
            if (statusText != null)
            {
                string pose = controls != null
                    ? $"Lens yaw {controls.YawDegrees:F1}  pitch {controls.PitchDegrees:F1}  roll {controls.RollDegrees:F1}"
                    : "No lens anchor bound";
                string observer = observerRigControls != null
                    ? observerRigControls.StatusText().Replace("\n", "  ")
                    : "Observer rig not bound";
                string disk = runtimeSettings != null
                    ? runtimeSettings.StatusText().Replace("\n", "  ")
                    : "No disk settings bound";
                // Spin and mass are the two controls that change the metric,
                // and they had no on-screen value anywhere: the operator could
                // move them with no way to read back what was set.
                var tracer = FindAnyObjectByType<BlackHoleLiveTracer>();
                string metric = tracer != null
                    ? $"Metric M={tracer.MassValue:F2}  a={tracer.SpinValue:F3}  live={tracer.LiveTracingEnabled}"
                    : "Metric: live tracer not bound";
                statusText.text =
                    $"{observer}\n{pose}\n{disk}\n{metric}\n" +
                    "Tier 0 playback: spin / inclination need GPU regenerate; r_obs roams keyframes.";
            }
            if (footerText != null)
            {
                footerText.text = "Stick selects   ·   A / trigger activates   ·   B or Close hides";
            }

            for (int i = 0; i < buttonImages.Count; i += 1)
            {
                bool selected = i == selectedIndex;
                buttonImages[i].color = selected ? ButtonSelected : ButtonNormal;
                buttonLabels[i].color = selected ? LabelSelected : LabelNormal;
            }
        }

        private void EnsureUi()
        {
            if (canvas != null)
            {
                return;
            }

            // Destroy stale serialized canvases first. An editor-time scene
            // save can persist the generated UI hierarchy, but its Button
            // listeners are non-persistent (AddListener) and are lost on
            // reload: the stale canvas then renders as an un-closable ghost
            // panel with dead buttons on top of the live one. Deferred Destroy
            // is only legal in play mode; the editor path is cleaned by
            // DestroyStaleCanvases from gate automation before saving.
            if (Application.isPlaying)
            {
                DestroyStaleCanvases();
            }

            var canvasObject = new GameObject("SettingsCanvas")
            {
                hideFlags = HideFlags.DontSave
            };
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
            background.sprite = GetRoundedSprite();
            background.type = Image.Type.Sliced;
            background.color = PanelBackground;

            var header = CreateImage("HeaderStrip", root, HeaderStrip);
            SetRect(header.rectTransform, new Vector2(0, 0), new Vector2(root.sizeDelta.x, 74), new Vector2(0, 1));

            titleText = CreateText("Title", root, "GR-BH-XR  ·  Kerr Roam", 30, TextAnchor.MiddleLeft);
            SetRect(titleText.rectTransform, new Vector2(28, -37), new Vector2(root.sizeDelta.x - 190, 46), new Vector2(0, 1));
            titleText.rectTransform.pivot = new Vector2(0.0f, 0.5f);
            titleText.rectTransform.anchoredPosition = new Vector2(28, -37);

            statusText = CreateText("Status", root, "", 15, TextAnchor.UpperLeft);
            statusText.color = StatusColor;
            SetRect(statusText.rectTransform, new Vector2(28, -88), new Vector2(root.sizeDelta.x - 56, 82), new Vector2(0, 1));

            actions.Clear();
            buttonLabels.Clear();
            buttonImages.Clear();
            AddButton(
                "Close",
                new Vector2(root.sizeDelta.x - 132.0f, -19.0f),
                new Vector2(108.0f, 38.0f),
                Close
            );

            layoutCursorY = -176.0f;
            AddSection("Observer");
            AddButton("Free Fall  (closes panel & drops)", NextRow(), () =>
            {
                observerRigControls?.StartFreeFall();
                Close();
            });
            AddTwoButtonRow("Live Tracing On/Off", "Live Res cycle", NextRow(),
                () => FindAnyObjectByType<BlackHoleLiveTracer>()?.ToggleLiveTracing(),
                () => FindAnyObjectByType<BlackHoleLiveTracer>()?.CycleResolution());
            AddButton("MR Passthrough On/Off  (room through the lens)", NextRow(),
                () => BlackHoleMrPassthrough.Ensure().ToggleMr());
            AddTwoButtonRow("Spin -0.1  (can go negative)", "Spin +0.1", NextRow(),
                () => FindAnyObjectByType<BlackHoleLiveTracer>()?.AdjustSpin(-0.1f),
                () => FindAnyObjectByType<BlackHoleLiveTracer>()?.AdjustSpin(0.1f));
            AddTwoButtonRow("Mass -0.1", "Mass +0.1", NextRow(),
                () => FindAnyObjectByType<BlackHoleLiveTracer>()?.AdjustMass(-0.1f),
                () => FindAnyObjectByType<BlackHoleLiveTracer>()?.AdjustMass(0.1f));
            AddTwoButtonRow("Move inward", "Move outward", NextRow(),
                () => observerRigControls?.AddRadialInput(1.0f, 0.6f),
                () => observerRigControls?.AddRadialInput(-1.0f, 0.6f));
            AddButton("Place Lens at View", NextRow(), () => controls?.ResetPose());

            AddSection("Disk");
            AddButton("Disk Visual On/Off", NextRow(), () => runtimeSettings?.ToggleDiskVisualMode());
            AddButton("Disk Audit Off / m0 / m1", NextRow(), () => runtimeSettings?.CycleDiskAuditMode());
            AddTwoButtonRow("Opacity -", "Opacity +", NextRow(),
                () => runtimeSettings?.AddDiskOpacity(-0.08f),
                () => runtimeSettings?.AddDiskOpacity(0.08f));
            AddTwoButtonRow("Brightness -", "Brightness +", NextRow(),
                () => runtimeSettings?.AddDiskBrightness(-0.15f),
                () => runtimeSettings?.AddDiskBrightness(0.15f));
            AddTwoButtonRow("g Power -", "g Power +", NextRow(),
                () => runtimeSettings?.AddDiskGPower(-0.25f),
                () => runtimeSettings?.AddDiskGPower(0.25f));

            AddSection("Hot Spot");
            AddTwoButtonRow("Hot Spot On/Off", "Orbit On/Off", NextRow(),
                () => runtimeSettings?.ToggleDiskHotSpot(),
                () => runtimeSettings?.ToggleDiskHotSpotAnimation());
            AddTwoButtonRow("Spot r -", "Spot r +", NextRow(),
                () => runtimeSettings?.AddDiskHotSpotRadius(-0.5f),
                () => runtimeSettings?.AddDiskHotSpotRadius(0.5f));
            AddTwoButtonRow("Spot phi -", "Spot phi +", NextRow(),
                () => runtimeSettings?.AddDiskHotSpotPhase(-0.15f),
                () => runtimeSettings?.AddDiskHotSpotPhase(0.15f));
            AddTwoButtonRow("Spot width -", "Spot width +", NextRow(),
                () => runtimeSettings?.AddDiskHotSpotWidth(-0.25f),
                () => runtimeSettings?.AddDiskHotSpotWidth(0.25f));
            AddTwoButtonRow("Spot dim", "Spot bright", NextRow(),
                () => runtimeSettings?.AddDiskHotSpotBrightness(-0.25f),
                () => runtimeSettings?.AddDiskHotSpotBrightness(0.25f));
            selectedIndex = actions.Count > 1 ? 1 : 0;

            footerText = CreateText("Footer", root, "", 14, TextAnchor.MiddleCenter);
            footerText.color = FooterColor;
            SetRect(footerText.rectTransform, new Vector2(28, 18), new Vector2(root.sizeDelta.x - 56, 30), new Vector2(0, 0));
            ApplyDontSaveRecursive(canvasObject.transform);
            canvasObject.SetActive(visible);
        }

        private float NextRow()
        {
            layoutCursorY -= 48.0f;
            return layoutCursorY;
        }

        private void AddSection(string label)
        {
            layoutCursorY -= 34.0f;
            var text = CreateText($"Section{label}", root, label.ToUpperInvariant(), 15, TextAnchor.LowerLeft);
            text.color = SectionColor;
            SetRect(text.rectTransform, new Vector2(28.0f, layoutCursorY), new Vector2(root.sizeDelta.x - 56.0f, 26.0f), new Vector2(0, 1));
            var divider = CreateImage($"Divider{label}", root, new Color(SectionColor.r, SectionColor.g, SectionColor.b, 0.25f));
            SetRect(divider.rectTransform, new Vector2(28.0f, layoutCursorY - 4.0f), new Vector2(root.sizeDelta.x - 56.0f, 2.0f), new Vector2(0, 1));
            layoutCursorY -= 8.0f;
        }

        private static void ApplyDontSaveRecursive(Transform node)
        {
            node.gameObject.hideFlags = HideFlags.DontSave;
            for (int i = 0; i < node.childCount; i += 1)
            {
                ApplyDontSaveRecursive(node.GetChild(i));
            }
        }

        public void DestroyStaleCanvases()
        {
            for (int i = transform.childCount - 1; i >= 0; i -= 1)
            {
                Transform child = transform.GetChild(i);
                if (child.name == "SettingsCanvas" && (canvas == null || child != canvas.transform))
                {
                    DestroyGameObject(child.gameObject);
                }
            }
        }

        private static void DestroyGameObject(GameObject target)
        {
            if (Application.isPlaying)
            {
                Destroy(target);
            }
            else
            {
                DestroyImmediate(target);
            }
        }

        private void AddButton(string label, float y, Action action)
        {
            AddButton(label, new Vector2(28.0f, y), new Vector2(root.sizeDelta.x - 56.0f, 40.0f), action);
        }

        private void AddTwoButtonRow(string leftLabel, string rightLabel, float y, Action leftAction, Action rightAction)
        {
            float width = (root.sizeDelta.x - 68.0f) * 0.5f;
            AddButton(leftLabel, new Vector2(28.0f, y), new Vector2(width, 40.0f), leftAction);
            AddButton(rightLabel, new Vector2(40.0f + width, y), new Vector2(width, 40.0f), rightAction);
        }

        private void AddButton(string label, Vector2 anchoredPosition, Vector2 size, Action action)
        {
            var buttonObject = new GameObject(label);
            buttonObject.transform.SetParent(root, worldPositionStays: false);
            var rect = buttonObject.AddComponent<RectTransform>();
            SetRect(rect, anchoredPosition, size, new Vector2(0, 1));
            var image = buttonObject.AddComponent<Image>();
            image.sprite = GetRoundedSprite();
            image.type = Image.Type.Sliced;
            var button = buttonObject.AddComponent<Button>();
            button.targetGraphic = image;
            button.onClick.AddListener(() => action?.Invoke());

            var text = CreateText("Label", rect, label, 16, TextAnchor.MiddleCenter);
            SetRect(text.rectTransform, Vector2.zero, size, new Vector2(0.5f, 0.5f));
            actions.Add(action);
            buttonLabels.Add(text);
            buttonImages.Add(image);
        }

        private static Image CreateImage(string name, Transform parent, Color color)
        {
            var imageObject = new GameObject(name);
            imageObject.transform.SetParent(parent, worldPositionStays: false);
            var image = imageObject.AddComponent<Image>();
            image.color = color;
            image.raycastTarget = false;
            return image;
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
            label.color = LabelNormal;
            return label;
        }

        /// <summary>
        /// Procedural rounded-rectangle 9-slice sprite so the panel needs no
        /// texture assets. Generated once, DontSave.
        /// </summary>
        private static Sprite GetRoundedSprite()
        {
            if (roundedSprite != null)
            {
                return roundedSprite;
            }
            const int size = 64;
            const int radius = 18;
            var texture = new Texture2D(size, size, TextureFormat.RGBA32, mipChain: false)
            {
                hideFlags = HideFlags.DontSave,
                wrapMode = TextureWrapMode.Clamp,
                filterMode = FilterMode.Bilinear
            };
            var pixels = new Color[size * size];
            for (int y = 0; y < size; y += 1)
            {
                for (int x = 0; x < size; x += 1)
                {
                    float clampedX = Mathf.Clamp(x, radius, size - 1 - radius);
                    float clampedY = Mathf.Clamp(y, radius, size - 1 - radius);
                    float distance = Mathf.Sqrt((x - clampedX) * (x - clampedX) + (y - clampedY) * (y - clampedY));
                    float alpha = Mathf.Clamp01(radius - distance + 0.5f);
                    pixels[y * size + x] = new Color(1.0f, 1.0f, 1.0f, alpha);
                }
            }
            texture.SetPixels(pixels);
            texture.Apply(updateMipmaps: false, makeNoLongerReadable: false);
            roundedSprite = Sprite.Create(
                texture,
                new Rect(0, 0, size, size),
                new Vector2(0.5f, 0.5f),
                100.0f,
                0,
                SpriteMeshType.FullRect,
                new Vector4(radius + 4, radius + 4, radius + 4, radius + 4)
            );
            roundedSprite.hideFlags = HideFlags.DontSave;
            return roundedSprite;
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
            if (observerRigControls == null)
            {
                observerRigControls = FindAnyObjectByType<BlackHoleObserverRigControls>();
            }
        }
    }
}
