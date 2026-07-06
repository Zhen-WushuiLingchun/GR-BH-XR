using System;
using UnityEngine;

namespace GRBHXR
{
    [Serializable]
    public sealed class LensMapMetadata
    {
        public string schema;
        public string sourceSchema;
        public int width;
        public int height;
        public int escapePixels;
        public ScreenConvention screenConvention;
        public ScreenBounds screen;
        public UnityBasis unityBasisInBhCoordinates;
    }

    [Serializable]
    public sealed class ScreenConvention
    {
        public string alphaColumnOrder;
        public string betaRowOrder;
        public string textureOrigin;
        public string positiveAlpha;
        public string positiveBeta;
    }

    [Serializable]
    public sealed class ScreenBounds
    {
        public float alphaMin;
        public float alphaMax;
        public float betaMin;
        public float betaMax;
    }

    [Serializable]
    public sealed class UnityBasis
    {
        public float[] rightBh;
        public float[] upBh;
        public float[] forwardBh;
        public string mapping;
    }

    public sealed class BlackHoleLensMap : MonoBehaviour
    {
        [Header("Exported Task 5 texture package")]
        [SerializeField] private TextAsset metadataJson;
        [SerializeField] private TextAsset eventRgba8Bytes;
        [SerializeField] private TextAsset escapeDirectionUnityRgba32fBytes;

        public LensMapMetadata Metadata { get; private set; }
        public Texture2D EventTexture { get; private set; }
        public Texture2D EscapeDirectionTexture { get; private set; }

        private void Awake()
        {
            Load();
        }

        public void Load()
        {
            if (metadataJson == null)
            {
                throw new InvalidOperationException("Lens-map metadata JSON is not assigned.");
            }

            Metadata = JsonUtility.FromJson<LensMapMetadata>(metadataJson.text);
            if (Metadata == null || Metadata.width <= 0 || Metadata.height <= 0)
            {
                throw new InvalidOperationException("Lens-map metadata is missing width/height.");
            }

            EventTexture = LoadRawTexture(
                eventRgba8Bytes,
                Metadata.width,
                Metadata.height,
                TextureFormat.RGBA32,
                expectedBytesPerPixel: 4,
                name: "GR-BH-XR event_rgba8"
            );
            EscapeDirectionTexture = LoadRawTexture(
                escapeDirectionUnityRgba32fBytes,
                Metadata.width,
                Metadata.height,
                TextureFormat.RGBAFloat,
                expectedBytesPerPixel: 16,
                name: "GR-BH-XR escape_dir_unity_rgba32f"
            );
        }

        public void ApplyToMaterial(Material material)
        {
            if (material == null)
            {
                return;
            }
            if (EventTexture == null || EscapeDirectionTexture == null)
            {
                Load();
            }
            material.SetTexture("_EventTex", EventTexture);
            material.SetTexture("_EscapeDirTex", EscapeDirectionTexture);
        }

        private static Texture2D LoadRawTexture(
            TextAsset bytes,
            int width,
            int height,
            TextureFormat format,
            int expectedBytesPerPixel,
            string name
        )
        {
            if (bytes == null)
            {
                throw new InvalidOperationException($"{name} bytes are not assigned.");
            }

            int expected = width * height * expectedBytesPerPixel;
            if (bytes.bytes.Length != expected)
            {
                throw new InvalidOperationException(
                    $"{name} has {bytes.bytes.Length} bytes; expected {expected}."
                );
            }

            var texture = new Texture2D(width, height, format, mipChain: false, linear: true)
            {
                name = name,
                wrapMode = TextureWrapMode.Clamp,
                filterMode = FilterMode.Bilinear
            };
            texture.LoadRawTextureData(bytes.bytes);
            texture.Apply(updateMipmaps: false, makeNoLongerReadable: true);
            return texture;
        }
    }
}
