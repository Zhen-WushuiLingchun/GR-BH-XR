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
            lensMap = GetComponent<BlackHoleLensMap>();
        }

        private void Start()
        {
            Bind();
        }

        private void LateUpdate()
        {
            if (refreshBasisEveryFrame)
            {
                lensMap.ApplyBasisToMaterial(targetMaterial);
            }
        }

        public void Bind()
        {
            lensMap.ApplyToMaterial(targetMaterial);
        }
    }
}
