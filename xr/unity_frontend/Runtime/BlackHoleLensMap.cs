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
        public int sourceEscapePixels;
        public int escapePixels;
        public ResolutionMetadata resolution;
        public ScreenConvention screenConvention;
        public ScreenBounds screen;
        public UnityBasis unityBasisInBhCoordinates;
        public SourceAttributes sourceAttributes;
    }

    [Serializable]
    public sealed class FullSkyTransferMetadata
    {
        public string schema;
        public int faceSize;
    }

    [Serializable]
    public sealed class DiskColorLutMetadata
    {
        public string schema;
        public int samples;
        public float temperatureMinK;
        public float temperatureMaxK;
        public string temperatureSpacing;
    }

    [Serializable]
    public sealed class DiskRadialLutMetadata
    {
        public string schema;
        public int samples;
        public float rMin;
        public float rMax;
        public float temperatureScaleK;
    }

    [Serializable]
    public sealed class ResolutionMetadata
    {
        public int sourceWidth;
        public int sourceHeight;
        public int exportWidth;
        public int exportHeight;
        public bool nativeTraceResolution;
        public string resampling;
        public string physicsNote;
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

    [Serializable]
    public sealed class SourceAttributes
    {
        public float r_obs;
    }

    public sealed class BlackHoleLensMap : MonoBehaviour
    {
        [Header("Exported Task 5 texture package")]
        [SerializeField] private TextAsset metadataJson;
        [SerializeField] private TextAsset eventRgba8Bytes;
        [SerializeField] private TextAsset escapeDirectionUnityRgba32fBytes;
        [Header("Optional full-sky transfer cubemap")]
        [SerializeField] private TextAsset fullSkyMetadataJson;
        [SerializeField] private TextAsset eventCubeRgba8Bytes;
        [SerializeField] private TextAsset escapeDirectionUnityCubeRgba32fBytes;
        [SerializeField] private TextAsset diskOrder0TransferCubeRgba16fBytes;
        [SerializeField] private TextAsset diskOrder1TransferCubeRgba16fBytes;
        [Header("Optional disk color and emissivity LUTs")]
        [SerializeField] private TextAsset diskColorLutMetadataJson;
        [SerializeField] private TextAsset diskColorLutRgba32fBytes;
        [SerializeField] private TextAsset diskRadialLutMetadataJson;
        [SerializeField] private TextAsset diskRadialLutRgba32fBytes;

        public LensMapMetadata Metadata { get; private set; }
        public FullSkyTransferMetadata FullSkyMetadata { get; private set; }
        public Texture2D EventTexture { get; private set; }
        public Texture2D EscapeDirectionTexture { get; private set; }
        public Cubemap EventCube { get; private set; }
        public Cubemap EscapeDirectionCube { get; private set; }
        public Cubemap DiskOrder0Cube { get; private set; }
        public Cubemap DiskOrder1Cube { get; private set; }
        public DiskColorLutMetadata DiskColorLutMetadata { get; private set; }
        public DiskRadialLutMetadata DiskRadialLutMetadata { get; private set; }
        public Texture2D DiskColorLutTexture { get; private set; }
        public Texture2D DiskRadialLutTexture { get; private set; }

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
                name: "GR-BH-XR event_rgba8",
                filterMode: FilterMode.Point
            );
            EscapeDirectionTexture = LoadRawTexture(
                escapeDirectionUnityRgba32fBytes,
                Metadata.width,
                Metadata.height,
                TextureFormat.RGBAFloat,
                expectedBytesPerPixel: 16,
                name: "GR-BH-XR escape_dir_unity_rgba32f",
                filterMode: FilterMode.Bilinear
            );
            LoadFullSkyCubemapIfPresent();
            LoadDiskLutsIfPresent();
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
            material.SetFloat("_UseFullSkyTransfer", EscapeDirectionCube != null ? 1.0f : 0.0f);
            if (EventCube != null)
            {
                material.SetTexture("_EventCube", EventCube);
            }
            if (EscapeDirectionCube != null)
            {
                material.SetTexture("_EscapeDirCube", EscapeDirectionCube);
            }
            material.SetFloat("_UseDiskTransfer", DiskOrder0Cube != null ? 1.0f : 0.0f);
            if (DiskOrder0Cube != null)
            {
                material.SetTexture("_DiskOrder0Cube", DiskOrder0Cube);
            }
            if (DiskOrder1Cube != null)
            {
                material.SetTexture("_DiskOrder1Cube", DiskOrder1Cube);
            }
            bool useDiskColorLut = DiskColorLutTexture != null && DiskRadialLutTexture != null;
            material.SetFloat("_UseDiskColorLut", useDiskColorLut ? 1.0f : 0.0f);
            if (useDiskColorLut)
            {
                material.SetTexture("_DiskColorLut", DiskColorLutTexture);
                material.SetTexture("_DiskRadialLut", DiskRadialLutTexture);
                material.SetVector(
                    "_DiskColorLutLogT",
                    new Vector4(
                        Mathf.Log(DiskColorLutMetadata.temperatureMinK),
                        Mathf.Log(DiskColorLutMetadata.temperatureMaxK),
                        0.0f,
                        0.0f
                    )
                );
                material.SetVector(
                    "_DiskRadialLutBounds",
                    new Vector4(DiskRadialLutMetadata.rMin, DiskRadialLutMetadata.rMax, 0.0f, 0.0f)
                );
                material.SetFloat("_DiskTemperatureScale", DiskRadialLutMetadata.temperatureScaleK);
            }
            if (Metadata.screen != null)
            {
                material.SetVector(
                    "_LensScreenBounds",
                    new Vector4(
                        Metadata.screen.alphaMin,
                        Metadata.screen.alphaMax,
                        Metadata.screen.betaMin,
                        Metadata.screen.betaMax
                    )
                );
            }
            material.SetFloat("_LensRObs", ObserverRadiusOrDefault());
            ApplyBasisToMaterial(material);
        }

        public void ApplyBasisToMaterial(Material material)
        {
            if (material == null)
            {
                return;
            }
            material.SetVector("_LensWorldRight", transform.rotation * Vector3.right);
            material.SetVector("_LensWorldUp", transform.rotation * Vector3.up);
            material.SetVector("_LensWorldForward", transform.rotation * Vector3.forward);
        }

        private float ObserverRadiusOrDefault()
        {
            if (Metadata != null && Metadata.sourceAttributes != null && Metadata.sourceAttributes.r_obs > 0.0f)
            {
                return Metadata.sourceAttributes.r_obs;
            }
            Debug.LogWarning(
                "Lens-map metadata is missing sourceAttributes.r_obs; falling back to _LensRObs = 100. " +
                "Angular-window previews may have the wrong scale."
            );
            return 100.0f;
        }

        private void LoadFullSkyCubemapIfPresent()
        {
            if (fullSkyMetadataJson == null || eventCubeRgba8Bytes == null || escapeDirectionUnityCubeRgba32fBytes == null)
            {
                FullSkyMetadata = null;
                EventCube = null;
                EscapeDirectionCube = null;
                DiskOrder0Cube = null;
                DiskOrder1Cube = null;
                return;
            }

            FullSkyMetadata = JsonUtility.FromJson<FullSkyTransferMetadata>(fullSkyMetadataJson.text);
            if (FullSkyMetadata == null || FullSkyMetadata.faceSize <= 0)
            {
                throw new InvalidOperationException("Full-sky transfer metadata is missing faceSize.");
            }
            EventCube = LoadRawCubemap(
                eventCubeRgba8Bytes,
                FullSkyMetadata.faceSize,
                TextureFormat.RGBA32,
                expectedBytesPerPixel: 4,
                name: "GR-BH-XR full-sky event_cube_rgba8",
                filterMode: FilterMode.Point
            );
            EscapeDirectionCube = LoadRawCubemap(
                escapeDirectionUnityCubeRgba32fBytes,
                FullSkyMetadata.faceSize,
                TextureFormat.RGBAFloat,
                expectedBytesPerPixel: 16,
                name: "GR-BH-XR full-sky escape_dir_unity_cube_rgba32f",
                filterMode: FilterMode.Bilinear
            );
            DiskOrder0Cube = LoadOptionalRawCubemap(
                diskOrder0TransferCubeRgba16fBytes,
                FullSkyMetadata.faceSize,
                TextureFormat.RGBAHalf,
                expectedBytesPerPixel: 8,
                name: "GR-BH-XR full-sky disk_order0_transfer_cube_rgba16f",
                filterMode: FilterMode.Bilinear
            );
            DiskOrder1Cube = LoadOptionalRawCubemap(
                diskOrder1TransferCubeRgba16fBytes,
                FullSkyMetadata.faceSize,
                TextureFormat.RGBAHalf,
                expectedBytesPerPixel: 8,
                name: "GR-BH-XR full-sky disk_order1_transfer_cube_rgba16f",
                filterMode: FilterMode.Bilinear
            );
        }

        private static Texture2D LoadRawTexture(
            TextAsset bytes,
            int width,
            int height,
            TextureFormat format,
            int expectedBytesPerPixel,
            string name,
            FilterMode filterMode
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
                filterMode = filterMode
            };
            texture.LoadRawTextureData(bytes.bytes);
            texture.Apply(updateMipmaps: false, makeNoLongerReadable: true);
            return texture;
        }

        private static Cubemap LoadRawCubemap(
            TextAsset bytes,
            int faceSize,
            TextureFormat format,
            int expectedBytesPerPixel,
            string name,
            FilterMode filterMode
        )
        {
            if (bytes == null)
            {
                throw new InvalidOperationException($"{name} bytes are not assigned.");
            }

            int faceBytes = faceSize * faceSize * expectedBytesPerPixel;
            int expected = faceBytes * 6;
            if (bytes.bytes.Length != expected)
            {
                throw new InvalidOperationException(
                    $"{name} has {bytes.bytes.Length} bytes; expected {expected}."
                );
            }

            var texture = new Cubemap(faceSize, format, mipChain: false)
            {
                name = name,
                wrapMode = TextureWrapMode.Clamp,
                filterMode = filterMode
            };
            var faces = new[]
            {
                CubemapFace.PositiveX,
                CubemapFace.NegativeX,
                CubemapFace.PositiveY,
                CubemapFace.NegativeY,
                CubemapFace.PositiveZ,
                CubemapFace.NegativeZ
            };
            for (int face = 0; face < faces.Length; face++)
            {
                var faceData = new byte[faceBytes];
                Buffer.BlockCopy(bytes.bytes, face * faceBytes, faceData, 0, faceBytes);
                texture.SetPixelData(faceData, 0, faces[face]);
            }
            texture.Apply(updateMipmaps: false, makeNoLongerReadable: true);
            return texture;
        }

        private static Cubemap LoadOptionalRawCubemap(
            TextAsset bytes,
            int faceSize,
            TextureFormat format,
            int expectedBytesPerPixel,
            string name,
            FilterMode filterMode
        )
        {
            if (bytes == null)
            {
                return null;
            }
            return LoadRawCubemap(bytes, faceSize, format, expectedBytesPerPixel, name, filterMode);
        }

        private void LoadDiskLutsIfPresent()
        {
            DiskColorLutMetadata = null;
            DiskRadialLutMetadata = null;
            DiskColorLutTexture = null;
            DiskRadialLutTexture = null;

            if (diskColorLutMetadataJson != null && diskColorLutRgba32fBytes != null)
            {
                DiskColorLutMetadata = JsonUtility.FromJson<DiskColorLutMetadata>(diskColorLutMetadataJson.text);
                if (DiskColorLutMetadata == null || DiskColorLutMetadata.samples < 2)
                {
                    throw new InvalidOperationException("Disk color LUT metadata is missing samples.");
                }
                DiskColorLutTexture = LoadRawTexture(
                    diskColorLutRgba32fBytes,
                    DiskColorLutMetadata.samples,
                    1,
                    TextureFormat.RGBAFloat,
                    expectedBytesPerPixel: 16,
                    name: "GR-BH-XR disk_color_lut_rgba32f",
                    filterMode: FilterMode.Bilinear
                );
            }

            if (diskRadialLutMetadataJson != null && diskRadialLutRgba32fBytes != null)
            {
                DiskRadialLutMetadata = JsonUtility.FromJson<DiskRadialLutMetadata>(diskRadialLutMetadataJson.text);
                if (DiskRadialLutMetadata == null || DiskRadialLutMetadata.samples < 2)
                {
                    throw new InvalidOperationException("Disk radial LUT metadata is missing samples.");
                }
                DiskRadialLutTexture = LoadRawTexture(
                    diskRadialLutRgba32fBytes,
                    DiskRadialLutMetadata.samples,
                    1,
                    TextureFormat.RGBAFloat,
                    expectedBytesPerPixel: 16,
                    name: "GR-BH-XR disk_radial_lut_rgba32f",
                    filterMode: FilterMode.Bilinear
                );
            }
        }
    }
}
