using UnityEngine;

namespace GRBHXR
{
    [RequireComponent(typeof(BlackHoleLensMap))]
    public sealed class BlackHoleLensMaterialBinder : MonoBehaviour
    {
        [SerializeField] private Material targetMaterial;
        [SerializeField] private bool refreshBasisEveryFrame = true;

        private BlackHoleLensMap lensMap;

        private void Awake()
        {
            TryResolveLensMap();
        }

        private void Start()
        {
            Bind();
        }

        private void LateUpdate()
        {
            if (refreshBasisEveryFrame && TryResolveLensMap())
            {
                lensMap.ApplyBasisToMaterial(targetMaterial);
            }
        }

        public void Bind()
        {
            if (TryResolveLensMap())
            {
                lensMap.ApplyToMaterial(targetMaterial);
            }
        }

        private bool TryResolveLensMap()
        {
            if (lensMap == null)
            {
                lensMap = GetComponent<BlackHoleLensMap>();
            }
            if (lensMap == null)
            {
                Debug.LogWarning("BlackHoleLensMaterialBinder could not find BlackHoleLensMap.");
                return false;
            }
            return true;
        }
    }
}
