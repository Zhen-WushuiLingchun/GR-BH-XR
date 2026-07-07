using UnityEngine;

namespace GRBHXR
{
    [ExecuteAlways]
    [RequireComponent(typeof(Renderer))]
    [RequireComponent(typeof(BlackHoleLensMap))]
    public sealed class BlackHoleXrSkyShell : MonoBehaviour
    {
        [SerializeField] private Camera targetCamera;
        [SerializeField] private Transform lensAnchor;
        [SerializeField] private BlackHoleLensMap lensMap;
        [SerializeField] private Material targetMaterial;
        [SerializeField] private float shellDiameter = 200.0f;
        [SerializeField] private bool followCameraPosition = true;
        [SerializeField] private bool refreshBasisEveryFrame = true;

        private Renderer cachedRenderer;

        private void Awake()
        {
            ResolveReferences();
        }

        private void OnEnable()
        {
            SyncNow();
        }

        private void LateUpdate()
        {
            SyncNow();
        }

        public void SyncNow()
        {
            ResolveReferences();

            if (targetCamera != null && followCameraPosition)
            {
                transform.position = targetCamera.transform.position;
            }

            if (lensAnchor != null)
            {
                transform.rotation = lensAnchor.rotation;
            }

            float diameter = Mathf.Max(shellDiameter, 1.0f);
            transform.localScale = new Vector3(diameter, diameter, diameter);

            if (refreshBasisEveryFrame && lensMap != null)
            {
                lensMap.ApplyBasisToMaterial(ResolvedMaterial());
            }
        }

        private void ResolveReferences()
        {
            if (targetCamera == null)
            {
                targetCamera = Camera.main;
            }
            if (lensMap == null)
            {
                lensMap = GetComponent<BlackHoleLensMap>();
            }
            if (cachedRenderer == null)
            {
                cachedRenderer = GetComponent<Renderer>();
            }
            if (targetMaterial == null && cachedRenderer != null)
            {
                targetMaterial = cachedRenderer.sharedMaterial;
            }
        }

        private Material ResolvedMaterial()
        {
            if (targetMaterial != null)
            {
                return targetMaterial;
            }
            return cachedRenderer != null ? cachedRenderer.sharedMaterial : null;
        }
    }
}
