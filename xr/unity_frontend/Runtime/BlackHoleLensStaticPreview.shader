Shader "GR-BH-XR/Kerr Lens Static Preview"
{
    Properties
    {
        _EventTex ("Event Texture", 2D) = "black" {}
        _EscapeDirTex ("Escape Direction Texture", 2D) = "black" {}
        _EventCube ("Full-Sky Event Cube", Cube) = "" {}
        _EscapeDirCube ("Full-Sky Escape Direction Cube", Cube) = "" {}
        _DiskOrder0Cube ("Disk Order 0 Transfer Cube", Cube) = "" {}
        _DiskOrder1Cube ("Disk Order 1 Transfer Cube", Cube) = "" {}
        _SkyboxCubemap ("Skybox Cubemap", Cube) = "" {}
        _LensScreenBounds ("Lens Screen Bounds", Vector) = (-8, 8, -8, 8)
        _LensRObs ("Lens Observer Radius", Float) = 100
        _UseAngularWindow ("Use Angular Window", Float) = 0
        _UseFullSkyTransfer ("Use Full-Sky Transfer", Float) = 0
        _UseDiskTransfer ("Use Disk Transfer", Float) = 0
        _DiskAuditMode ("Disk Audit Mode", Float) = 0
        _DiskVisualMode ("Disk Visual Mode", Float) = 0
        _DiskOpacity ("Disk Opacity", Float) = 0.85
        _DiskBrightness ("Disk Brightness", Float) = 1.0
        _DiskGPower ("Disk g Power", Float) = 3.0
        _DiskSecondaryScale ("Disk Secondary Scale", Float) = 0.32
        _ProbeMode ("Probe Mode", Float) = 0
        _SkyboxLodBias ("Skybox LOD Bias", Float) = 0
        _StrongLensLodBias ("Strong Lens LOD Bias", Float) = 0.85
        _LensWorldRight ("Lens World Right", Vector) = (1, 0, 0, 0)
        _LensWorldUp ("Lens World Up", Vector) = (0, 1, 0, 0)
        _LensWorldForward ("Lens World Forward", Vector) = (0, 0, 1, 0)
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        Pass
        {
            Cull Off
            // ZWrite must stay ON: the built-in pipeline draws the camera skybox
            // after opaques wherever depth is still at the far plane. With ZWrite
            // off, the sky shell leaves depth untouched and the raw skybox pass
            // overwrites the entire lensed image in the player.
            ZWrite On
            ZTest Always

            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.0
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"

            sampler2D _EventTex;
            sampler2D _EscapeDirTex;
            samplerCUBE _EventCube;
            samplerCUBE _EscapeDirCube;
            samplerCUBE _DiskOrder0Cube;
            samplerCUBE _DiskOrder1Cube;
            samplerCUBE _SkyboxCubemap;
            float4 _LensScreenBounds;
            float _LensRObs;
            float _UseAngularWindow;
            float _UseFullSkyTransfer;
            float _UseDiskTransfer;
            float _DiskAuditMode;
            float _DiskVisualMode;
            float _DiskOpacity;
            float _DiskBrightness;
            float _DiskGPower;
            float _DiskSecondaryScale;
            float _ProbeMode;
            float _SkyboxLodBias;
            float _StrongLensLodBias;
            float4 _LensWorldRight;
            float4 _LensWorldUp;
            float4 _LensWorldForward;

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 worldPos : TEXCOORD1;
                float4 screenPos : TEXCOORD2;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                o.worldPos = mul(unity_ObjectToWorld, v.vertex).xyz;
                o.screenPos = ComputeScreenPos(o.vertex);
                return o;
            }

            float3 lensDirectionToWorld(float3 direction)
            {
                return normalize(
                    normalize(_LensWorldRight.xyz) * direction.x +
                    normalize(_LensWorldUp.xyz) * direction.y +
                    normalize(_LensWorldForward.xyz) * direction.z
                );
            }

            float3 worldDirectionToLens(float3 direction)
            {
                float3 world = normalize(direction);
                return normalize(float3(
                    dot(world, normalize(_LensWorldRight.xyz)),
                    dot(world, normalize(_LensWorldUp.xyz)),
                    dot(world, normalize(_LensWorldForward.xyz))
                ));
            }

            fixed4 protractorProbe(float3 direction)
            {
                float thetaDeg = degrees(acos(clamp(normalize(direction).z, -1.0, 1.0)));
                float band = clamp(floor(thetaDeg / 10.0), 0.0, 17.0);
                float encoded = (band + 0.5) / 18.0;
                return fixed4(encoded, 0.0, 1.0 - encoded, 1.0);
            }

            fixed4 sampleSkybox(float3 direction, float lodBias)
            {
                return texCUBEbias(_SkyboxCubemap, float4(normalize(direction), lodBias));
            }

            bool diskSampleValid(float4 disk)
            {
                return disk.x > 1.0 && disk.w > 0.05;
            }

            fixed4 diskAuditColor(float4 disk, float order)
            {
                if (!diskSampleValid(disk))
                {
                    return fixed4(0.0, 0.0, 0.0, 1.0);
                }
                float g = saturate((disk.w - 0.45) / 0.95);
                float3 color = lerp(float3(0.08, 0.22, 1.0), float3(1.0, 0.18, 0.04), g);
                if (order > 0.5)
                {
                    color = lerp(color, float3(1.0, 0.15, 0.95), 0.35);
                }
                float radiusPhase = frac(disk.x / 2.0);
                float radiusDistance = min(radiusPhase, 1.0 - radiusPhase);
                float radialLine = smoothstep(0.015, 0.055, radiusDistance);
                color = lerp(float3(0.0, 0.0, 0.0), color, radialLine);
                return fixed4(color, 1.0);
            }

            float3 blackbodyRamp(float g)
            {
                float t = saturate((g - 0.45) / 1.05);
                float3 red = float3(1.0, 0.18, 0.04);
                float3 gold = float3(1.0, 0.63, 0.18);
                float3 white = float3(1.0, 0.95, 0.78);
                float3 blue = float3(0.58, 0.72, 1.0);
                float3 warm = lerp(red, gold, smoothstep(0.0, 0.45, t));
                float3 hot = lerp(white, blue, smoothstep(0.65, 1.0, t));
                return lerp(warm, hot, smoothstep(0.42, 0.82, t));
            }

            fixed4 diskVisualLayer(float4 disk, float order)
            {
                if (!diskSampleValid(disk))
                {
                    return fixed4(0.0, 0.0, 0.0, 0.0);
                }

                float r = max(disk.x, 1.0e-3);
                float g = clamp(disk.w, 0.05, 3.0);
                float innerGate = smoothstep(1.8, 2.8, r);
                float outerGate = 1.0 - smoothstep(27.0, 30.0, r);
                float emissivity = pow(saturate(6.0 / r), 2.2) * innerGate * outerGate;
                float orderScale = order > 0.5 ? _DiskSecondaryScale : 1.0;
                float observedWeight = emissivity * pow(g, max(_DiskGPower, 0.0)) * _DiskBrightness * orderScale;

                // This first visual mode is a documented thin-disk emissivity
                // proxy over the validated (r_m, phi_m, g_m) transfer map. It is
                // not yet a Page-Thorne flux model or radiative-transfer result.
                float3 color = blackbodyRamp(g) * observedWeight;
                float alpha = saturate(observedWeight * _DiskOpacity);
                return fixed4(color, alpha);
            }

            fixed4 compositeDiskVisual(fixed4 baseColor, float3 localRay)
            {
                if (_UseDiskTransfer <= 0.5 || _DiskVisualMode <= 0.5)
                {
                    return baseColor;
                }
                float4 disk1 = texCUBE(_DiskOrder1Cube, localRay);
                float4 disk0 = texCUBE(_DiskOrder0Cube, localRay);
                fixed4 layer1 = diskVisualLayer(disk1, 1.0);
                fixed4 layer0 = diskVisualLayer(disk0, 0.0);
                float3 rgb = baseColor.rgb;
                rgb = saturate(rgb + layer1.rgb * layer1.a);
                rgb = saturate(rgb + layer0.rgb * layer0.a);
                return fixed4(rgb, baseColor.a);
            }

            fixed4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                float3 worldRay = normalize(i.worldPos - _WorldSpaceCameraPos);
                float3 localRay = worldDirectionToLens(worldRay);
                float alphaMin = _LensScreenBounds.x;
                float alphaMax = _LensScreenBounds.y;
                float betaMin = _LensScreenBounds.z;
                float betaMax = _LensScreenBounds.w;
                if (_UseDiskTransfer > 0.5 && _DiskAuditMode > 0.5)
                {
                    float4 disk0 = texCUBE(_DiskOrder0Cube, localRay);
                    float4 disk1 = texCUBE(_DiskOrder1Cube, localRay);
                    return _DiskAuditMode > 1.5 ? diskAuditColor(disk1, 1.0) : diskAuditColor(disk0, 0.0);
                }

                fixed4 fullSkyColor = fixed4(0.0, 0.0, 0.0, 1.0);
                if (_UseFullSkyTransfer > 0.5)
                {
                    float4 cubeDir = texCUBE(_EscapeDirCube, localRay);
                    fixed4 cubeEvent = texCUBE(_EventCube, localRay);
                    if (cubeDir.a < 0.5)
                    {
                        fullSkyColor = cubeEvent;
                    }
                    else
                    {
                        float3 cubeWorldDir = lensDirectionToWorld(cubeDir.xyz);
                        fullSkyColor = _ProbeMode > 0.5
                            ? protractorProbe(cubeWorldDir)
                            : sampleSkybox(cubeWorldDir, _SkyboxLodBias);
                    }
                }

                float2 lensUv = float2(0.0, 0.0);
                bool insideAngularWindow = false;
                if (_UseAngularWindow > 0.5)
                {
                    if (localRay.z > 1.0e-5)
                    {
                        float alpha = _LensRObs * localRay.x / localRay.z;
                        float beta = -_LensRObs * localRay.y / localRay.z;
                        insideAngularWindow =
                            alpha >= alphaMin && alpha <= alphaMax &&
                            beta >= betaMin && beta <= betaMax;
                        if (insideAngularWindow)
                        {
                            lensUv = float2(
                                (alpha - alphaMin) / max(alphaMax - alphaMin, 1.0e-5),
                                (betaMax - beta) / max(betaMax - betaMin, 1.0e-5)
                            );
                        }
                    }
                }
                else
                {
                    float2 screenUv = i.screenPos.xy / max(i.screenPos.w, 1.0e-5);
                    float aspect = _ScreenParams.x / max(_ScreenParams.y, 1.0);
                    lensUv = float2((screenUv.x - 0.5) * aspect + 0.5, screenUv.y);
                    insideAngularWindow =
                        lensUv.x >= 0.0 && lensUv.x <= 1.0 &&
                        lensUv.y >= 0.0 && lensUv.y <= 1.0;
                }

                if (!insideAngularWindow)
                {
                    fixed4 baseColor = _UseFullSkyTransfer > 0.5 ? fullSkyColor : sampleSkybox(worldRay, _SkyboxLodBias);
                    return compositeDiskVisual(baseColor, localRay);
                }

                float4 dir = tex2D(_EscapeDirTex, lensUv);
                fixed4 eventColor = tex2D(_EventTex, lensUv);
                if (dir.a < 0.5)
                {
                    return compositeDiskVisual(eventColor, localRay);
                }
                float3 worldDir = lensDirectionToWorld(dir.xyz);
                if (_ProbeMode > 0.5)
                {
                    return protractorProbe(worldDir);
                }
                fixed4 localColor = sampleSkybox(worldDir, _StrongLensLodBias);
                if (_UseFullSkyTransfer > 0.5)
                {
                    float edgeDistance = min(min(lensUv.x, 1.0 - lensUv.x), min(lensUv.y, 1.0 - lensUv.y));
                    float localWeight = smoothstep(0.0, 0.04, edgeDistance);
                    return compositeDiskVisual(lerp(fullSkyColor, localColor, localWeight), localRay);
                }
                return compositeDiskVisual(localColor, localRay);
            }
            ENDCG
        }
    }
}
