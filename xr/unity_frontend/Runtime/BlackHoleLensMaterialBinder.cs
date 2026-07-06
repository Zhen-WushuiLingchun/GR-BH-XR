using UnityEngine;

namespace GRBHXR
{
    [RequireComponent(typeof(BlackHoleLensMap))]
    public sealed class BlackHoleLensMaterialBinder : MonoBehaviour
    {
        [SerializeField] private Material targetMaterial;

        private void Start()
        {
            Bind();
        }

        public void Bind()
        {
            var lensMap = GetComponent<BlackHoleLensMap>();
            lensMap.ApplyToMaterial(targetMaterial);
        }
    }
}
