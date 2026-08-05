Shader "GR-BH-XR/Kerr Lens Static Preview"
{
    Properties
    {
        _EventTex ("Event Texture", 2D) = "black" {}
        _EscapeDirTex ("Escape Direction Texture", 2D) = "black" {}
        _UseLiveWindow ("Use Live Window", Float) = 0
        _WindowDisk0Tex ("Live Window Disk Order 0", 2D) = "black" {}
        _WindowDisk1Tex ("Live Window Disk Order 1", 2D) = "black" {}
        _WindowRedshift0Tex ("Live Window Redshift Order 0", 2D) = "black" {}
        _WindowRedshift1Tex ("Live Window Redshift Order 1", 2D) = "black" {}
        _EventCube ("Full-Sky Event Cube", Cube) = "" {}
        _EscapeDirCube ("Full-Sky Escape Direction Cube", Cube) = "" {}
        _DiskOrder0Cube ("Disk Order 0 Transfer Cube", Cube) = "" {}
        _DiskOrder1Cube ("Disk Order 1 Transfer Cube", Cube) = "" {}
        _DiskOrder0RedshiftCube ("Disk Order 0 Redshift Cube", Cube) = "" {}
        _DiskOrder1RedshiftCube ("Disk Order 1 Redshift Cube", Cube) = "" {}
        _DiskColorLut ("Disk Blackbody Color LUT", 2D) = "white" {}
        _DiskRadialLut ("Disk Page-Thorne Radial LUT", 2D) = "black" {}
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
        _UseDiskCoverageTransfer ("Use Disk Coverage Transfer", Float) = 0
        _UseDiskColorLut ("Use Disk Color LUT", Float) = 0
        _DiskTemperatureScale ("Disk Temperature Scale K", Float) = 6500
        // .xy = log(T_min), log(T_max) / r_min, r_max; .z = LUT row count
        // (`samples`) for the endpoint-row texel coordinate, 0 = legacy asset.
        _DiskColorLutLogT ("Disk Color LUT logT/samples", Vector) = (6.907755, 10.596635, 0, 0)
        _DiskRadialLutBounds ("Disk Radial LUT Bounds/samples", Vector) = (2.320883, 30, 0, 0)
        _DiskHotSpotEnabled ("Disk Hot Spot Enabled", Float) = 0
        _DiskHotSpotAnimate ("Disk Hot Spot Animate", Float) = 0
        _DiskHotSpotRadius ("Disk Hot Spot Radius", Float) = 8
        _DiskHotSpotPhase ("Disk Hot Spot Phase", Float) = 0
        _DiskHotSpotSigmaR ("Disk Hot Spot Sigma R", Float) = 1
        _DiskHotSpotSigmaPhi ("Disk Hot Spot Sigma Phi", Float) = 0.18
        _DiskHotSpotBrightness ("Disk Hot Spot Brightness", Float) = 2
        _DiskHotSpotOmega ("Disk Hot Spot Omega", Float) = 0.04
        _ProbeMode ("Probe Mode", Float) = 0
        _SkyBlueshift ("Sky Blueshift (static observer)", Float) = 1
        _UseSkyChromaticShift ("Use Sky Chromatic Shift", Float) = 0
        _UseMrPassthrough ("Use MR Passthrough", Float) = 0
        _MrCameraTex ("MR Passthrough Camera", 2D) = "black" {}
        _MrCamRight ("MR Camera Right", Vector) = (1, 0, 0, 0)
        _MrCamUp ("MR Camera Up", Vector) = (0, 1, 0, 0)
        _MrCamForward ("MR Camera Forward", Vector) = (0, 0, 1, 0)
        _MrCamParams ("MR Camera tanHalfX/tanHalfY/vFlip/starFallback", Vector) = (1, 1, 0, 1)
        _MrCamProjection ("MR Camera sx/sy/ox/oy", Vector) = (0.5, 0.5, 0.5, 0.5)
        _MrFinite ("MR Finite Room enable/radius m", Vector) = (0, 2.5, 0, 0)
        _MrHolePosRel ("MR Hole Position rel head (m)", Vector) = (0, 0, 2, 0)
        _ObsEInf ("Observer E-inf Uniform A", Vector) = (0, 0, 0, 1)
        _ObsEInfB ("Observer E-inf Uniform B", Vector) = (0, 0, 0, 1)
        _RoamBlend ("Roam Crossfade Weight", Float) = 0
        _EventCubeB ("Blend Event Cube", Cube) = "" {}
        _EscapeDirCubeB ("Blend Escape Direction Cube", Cube) = "" {}
        _DiskOrder0CubeB ("Blend Disk Order 0 Cube", Cube) = "" {}
        _DiskOrder1CubeB ("Blend Disk Order 1 Cube", Cube) = "" {}
        _DiskOrder0RedshiftCubeB ("Blend Disk Order 0 Redshift Cube", Cube) = "" {}
        _DiskOrder1RedshiftCubeB ("Blend Disk Order 1 Redshift Cube", Cube) = "" {}
        _LensWorldRightB ("Blend Lens World Right", Vector) = (1, 0, 0, 0)
        _LensWorldUpB ("Blend Lens World Up", Vector) = (0, 1, 0, 0)
        _LensWorldForwardB ("Blend Lens World Forward", Vector) = (0, 0, 1, 0)
        _DiskObserverAzimuth ("Disk Observer Azimuth (rad)", Float) = 0
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
            // Roam crossfade: a second keyframe set is bound and the final
            // colors dissolve by _RoamBlend. The legacy 2D hybrid path is
            // compiled out in this variant to stay within sampler limits.
            #pragma multi_compile __ GRBHXR_ROAM_BLEND
            #include "UnityCG.cginc"

            #ifndef GRBHXR_ROAM_BLEND
            sampler2D _EventTex;
            sampler2D _EscapeDirTex;
            // Live high-resolution angular window disk layers (the sky share
            // reuses the legacy _EscapeDirTex/_EventTex sampler slots).
            sampler2D _WindowDisk0Tex;
            sampler2D _WindowDisk1Tex;
            sampler2D _WindowRedshift0Tex;
            sampler2D _WindowRedshift1Tex;
            // MR passthrough camera (real room). Compiled out of the blend
            // variant to stay within the 16-sampler limit.
            sampler2D _MrCameraTex;
            #endif
            float _UseLiveWindow;
            float _UseMrPassthrough;
            float4 _MrCamRight;
            float4 _MrCamUp;
            float4 _MrCamForward;
            float4 _MrCamParams;
            float4 _MrCamProjection;
            float4 _MrFinite;
            float4 _MrHolePosRel;
            samplerCUBE _EventCube;
            samplerCUBE _EscapeDirCube;
            samplerCUBE _DiskOrder0Cube;
            samplerCUBE _DiskOrder1Cube;
            samplerCUBE _DiskOrder0RedshiftCube;
            samplerCUBE _DiskOrder1RedshiftCube;
            #ifdef GRBHXR_ROAM_BLEND
            samplerCUBE _EventCubeB;
            samplerCUBE _EscapeDirCubeB;
            samplerCUBE _DiskOrder0CubeB;
            samplerCUBE _DiskOrder1CubeB;
            samplerCUBE _DiskOrder0RedshiftCubeB;
            samplerCUBE _DiskOrder1RedshiftCubeB;
            #endif
            sampler2D _DiskColorLut;
            sampler2D _DiskRadialLut;
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
            float _UseDiskCoverageTransfer;
            float _UseDiskColorLut;
            float _DiskTemperatureScale;
            float4 _DiskColorLutLogT;
            float4 _DiskRadialLutBounds;
            float _DiskHotSpotEnabled;
            float _DiskHotSpotAnimate;
            float _DiskHotSpotRadius;
            float _DiskHotSpotPhase;
            float _DiskHotSpotSigmaR;
            float _DiskHotSpotSigmaPhi;
            float _DiskHotSpotBrightness;
            float _DiskHotSpotOmega;
            float _ProbeMode;
            float _SkyBlueshift;
            float _UseSkyChromaticShift;
            float4 _ObsEInf;
            float4 _ObsEInfB;
            float _RoamBlend;
            float4 _LensWorldRightB;
            float4 _LensWorldUpB;
            float4 _LensWorldForwardB;
            float _DiskObserverAzimuth;
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

            float3 basisDirectionToWorld(float3 direction, float3 right, float3 up, float3 forward)
            {
                return normalize(
                    normalize(right) * direction.x +
                    normalize(up) * direction.y +
                    normalize(forward) * direction.z
                );
            }

            float3 worldDirectionToBasis(float3 direction, float3 right, float3 up, float3 forward)
            {
                float3 world = normalize(direction);
                return normalize(float3(
                    dot(world, normalize(right)),
                    dot(world, normalize(up)),
                    dot(world, normalize(forward))
                ));
            }

            float3 lensDirectionToWorld(float3 direction)
            {
                return basisDirectionToWorld(direction, _LensWorldRight.xyz, _LensWorldUp.xyz, _LensWorldForward.xyz);
            }

            float3 worldDirectionToLens(float3 direction)
            {
                return worldDirectionToBasis(direction, _LensWorldRight.xyz, _LensWorldUp.xyz, _LensWorldForward.xyz);
            }

            // Per-pixel observer-side factor: the launcher normalizes
            // -p.u_obs = 1, so an arriving photon with conserved energy
            // E_inf is observed scaled by 1/E_inf. E_inf(d) is exactly affine
            // in the local view direction for any stationary observer, so the
            // four per-keyframe constants are a packing identity, not a fit.
            // The retracted "2.7e-8" figure is not used: it is arithmetically
            // impossible for a float32 max-abs over this range and was never
            // produced by committed code. The committed float32 bound is
            // 4 ULP = 4.8e-7 (measured 1.196e-7, exactly one ULP), gated by
            // `gr_bh_xr.gpu.validate_descent_frames` in the physics worktree.
            float observerFactor(float3 localRay, float4 eInf)
            {
                float eInfValue = eInf.w + dot(localRay, eInf.xyz);
                return 1.0 / max(eInfValue, 1.0e-3);
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

            #ifndef GRBHXR_ROAM_BLEND
            // MR passthrough background: the escape direction samples the
            // REAL room through the headset's forward passthrough camera.
            // The supported MRUK backend supplies capture-time pose and
            // calibrated projection; the Windows virtual camera is legacy
            // diagnostics only. Room light enters the same bending/redshift
            // chain as the star field. A
            // single forward camera covers only its own cone: directions
            // outside it (strongly wound rays exiting backward) fall back to
            // the star field or to black ("no data"), a documented physical
            // boundary of the one-camera rig. A finite-room sphere supplies
            // the current near-field correction; XR_META_environment_depth
            // acquisition is live but shader-side re-intersection is a later
            // gate.
            fixed4 sampleBackground(float3 direction, float3 viewDirection, float lodBias)
            {
                if (_UseMrPassthrough > 0.5)
                {
                    float3 d = normalize(direction);
                    // Finite-room correction: strongly bent rays effectively
                    // leave the strong-field region at the HOLE's room
                    // position, not at the head; undeflected rays leave from
                    // the head. Weight the re-anchoring by the deflection
                    // angle (ramps in over ~8 deg of bending), intersect a
                    // head-centered room sphere (radius calibratable; the
                    // structured-light depth path replaces this sphere), and
                    // sample the camera toward that finite point. This
                    // removes the dominant hole-to-head parallax error of
                    // the infinity model without shifting the direct view.
                    if (_MrFinite.x > 0.5)
                    {
                        float deflection = 1.0 - saturate(dot(d, normalize(viewDirection)));
                        float anchorWeight = saturate(deflection / 0.01);
                        float3 rayOrigin = _MrHolePosRel.xyz * anchorWeight;
                        float b = dot(rayOrigin, d);
                        float c = dot(rayOrigin, rayOrigin) - _MrFinite.y * _MrFinite.y;
                        float t = -b + sqrt(max(b * b - c, 0.0));
                        d = normalize(rayOrigin + t * d);
                    }
                    float zc = dot(d, _MrCamForward.xyz);
                    if (zc > 1.0e-4)
                    {
                        float xc = dot(d, _MrCamRight.xyz) / zc;
                        float yc = dot(d, _MrCamUp.xyz) / zc;
                        // Calibrated pinhole map. MRUK supplies focal length,
                        // principal point, and crop-derived scale/offset;
                        // the legacy backend synthesizes the same form from
                        // its configured horizontal FOV.
                        float u = _MrCamProjection.z + _MrCamProjection.x * xc;
                        float v = _MrCamProjection.w + _MrCamProjection.y * yc;
                        if (_MrCamParams.z > 0.5)
                        {
                            v = 1.0 - v;
                        }
                        if (u > 0.0 && u < 1.0 && v > 0.0 && v < 1.0)
                        {
                            return tex2D(_MrCameraTex, float2(u, v));
                        }
                        // Fallback mode 2: clamp to the camera frame edge so
                        // the passthrough fills the whole forward view (a
                        // documented stretch band, not data).
                        if (_MrCamParams.w > 1.5)
                        {
                            return tex2D(_MrCameraTex, float2(saturate(u), saturate(v)));
                        }
                    }
                    // Fallback mode 0 (and behind-camera in mode 2): black.
                    if (_MrCamParams.w < 0.5 || _MrCamParams.w > 1.5)
                    {
                        return fixed4(0.0, 0.0, 0.0, 1.0);
                    }
                }
                return sampleSkybox(direction, lodBias);
            }
            #endif

            float4 unpackDiskSample(float4 transfer, float4 redshift, out float coverage)
            {
                if (_UseDiskCoverageTransfer > 0.5)
                {
                    coverage = saturate(transfer.w);
                    if (coverage <= 1.0e-4)
                    {
                        return float4(0.0, 0.0, 0.0, 0.0);
                    }
                    float invCoverage = 1.0 / coverage;
                    return float4(
                        transfer.x * invCoverage,
                        transfer.y * invCoverage,
                        transfer.z * invCoverage,
                        redshift.x * invCoverage
                    );
                }
                coverage = (transfer.x > 1.0 && transfer.w > 0.05) ? 1.0 : 0.0;
                return transfer;
            }

            bool diskSampleValid(float4 disk, float coverage)
            {
                return coverage > 1.0e-4 && disk.x > 1.0 && disk.w > 0.05;
            }

            fixed4 diskAuditColor(float4 disk, float order, float coverage)
            {
                if (!diskSampleValid(disk, coverage))
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
                color = lerp(float3(0.0, 0.0, 0.0), color, radialLine) * coverage;
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

            // Endpoint-row texel coordinate published by the LUT producer
            // (`disk_spectrum.py`, metadata key `radiusCoordinateExact` /
            // `rgbCoordinateExact`): row i of a `samples`-row LUT holds the
            // value at normalized parameter s = i / (samples - 1), so the
            // coordinate that lands exactly on that row is
            //     u = (s * (samples - 1) + 0.5) / samples
            // Sampling with u = s is a half-texel offset: 0.72% in effective
            // temperature at samples = 256 and 0.027 M in radius (0.048 in
            // normalized flux) at samples = 512. `samples` arrives in the .z
            // slot; a legacy asset that does not publish it (samples < 2)
            // keeps the old u = s mapping rather than silently rescaling.
            float lutRowCoordinate(float s, float samples)
            {
                if (samples < 2.0)
                {
                    return s;
                }
                return (s * (samples - 1.0) + 0.5) / samples;
            }

            float4 sampleDiskRadialLut(float r)
            {
                float s = saturate((r - _DiskRadialLutBounds.x) / max(_DiskRadialLutBounds.y - _DiskRadialLutBounds.x, 1.0e-5));
                return tex2D(_DiskRadialLut, float2(lutRowCoordinate(s, _DiskRadialLutBounds.z), 0.5));
            }

            float3 sampleDiskColorLut(float observedTemperatureK)
            {
                float logT = log(max(observedTemperatureK, 1.0));
                float s = saturate((logT - _DiskColorLutLogT.x) / max(_DiskColorLutLogT.y - _DiskColorLutLogT.x, 1.0e-5));
                return tex2D(_DiskColorLut, float2(lutRowCoordinate(s, _DiskColorLutLogT.z), 0.5)).rgb;
            }

            // Observer-side sky shading: bolometric g^4 brightness plus the
            // chromatic shift of the background. Emitter model: each sky
            // texel is a blackbody whose temperature is fitted from its own
            // chromaticity through the LUT alpha channel (inverse Planck
            // locus, schema v2). The observed color is
            //   rgb * LUT(T_emit * g) / LUT(T_emit)
            // with g the per-pixel observer factor; the ratio form is exactly
            // the identity at g = 1, so an imperfect temperature fit cannot
            // distort the unshifted sky. Brightness gain stays tone-capped at
            // 2^4 (display exposure only; the hue shift is uncapped within
            // the LUT range).
            float3 applySkyObserver(float3 rgb, float obsFactor)
            {
                float boost = pow(min(obsFactor, 2.0), 4.0);
                if (_UseSkyChromaticShift > 0.5)
                {
                    float chroma = rgb.r / max(rgb.r + rgb.b, 1.0e-5);
                    // No endpoint-row correction here, deliberately: the alpha
                    // channel is already resampled at texel centers of
                    // u = R/(R+B) by the producer (metadata `alphaCoordinate`),
                    // so a direct u = chroma fetch is the correct consumer.
                    float tNorm = tex2D(_DiskColorLut, float2(chroma, 0.5)).a;
                    float tEmit = exp(lerp(_DiskColorLutLogT.x, _DiskColorLutLogT.y, tNorm));
                    float3 hueEmit = sampleDiskColorLut(tEmit);
                    float3 hueObs = sampleDiskColorLut(tEmit * obsFactor);
                    rgb = rgb * hueObs / max(hueEmit, 1.0e-4);
                }
                return saturate(rgb * boost);
            }

            float diskHotSpotWeight(float4 disk, float coverage)
            {
                if (_DiskHotSpotEnabled <= 0.5 || !diskSampleValid(disk, coverage))
                {
                    return 0.0;
                }
                // Stored phi_m is azimuth relative to the traced observer
                // azimuth; subtracting the live observer azimuth keeps the
                // hot spot fixed in the black-hole frame while the observer
                // orbits (axisymmetric basis rotation).
                float phase = _DiskHotSpotPhase
                    + (_DiskHotSpotAnimate > 0.5 ? _DiskHotSpotOmega * _Time.y : 0.0)
                    - _DiskObserverAzimuth;
                float sinPhi = disk.y;
                float cosPhi = disk.z;
                float sinPhase = sin(phase);
                float cosPhase = cos(phase);
                float sinDelta = sinPhi * cosPhase - cosPhi * sinPhase;
                float cosDelta = cosPhi * cosPhase + sinPhi * sinPhase;
                float dPhi = atan2(sinDelta, cosDelta);
                float dR = (disk.x - _DiskHotSpotRadius) / max(_DiskHotSpotSigmaR, 1.0e-3);
                float dA = dPhi / max(_DiskHotSpotSigmaPhi, 1.0e-3);
                return exp(-0.5 * (dR * dR + dA * dA));
            }

            fixed4 diskVisualLayer(float4 disk, float order, float coverage, float obsFactor)
            {
                if (!diskSampleValid(disk, coverage))
                {
                    return fixed4(0.0, 0.0, 0.0, 0.0);
                }

                float r = max(disk.x, 1.0e-3);
                // Recorded g_m is the emitter-to-infinity factor; the
                // observer-side factor 1/E_inf completes the physical chain.
                // Direction-independent for a static observer; direction
                // dependent for a falling one. Whether the falling-frame
                // constants are correct is a property of their producer (the
                // Task 7-8 physics worktree), not of this shader.
                float g = clamp(disk.w * obsFactor, 0.05, 3.0);
                float orderScale = order > 0.5 ? _DiskSecondaryScale : 1.0;
                float usePhysicalColor = _UseDiskColorLut > 0.5 ? 1.0 : 0.0;
                float4 radialModel = sampleDiskRadialLut(r);
                float fluxShape = max(radialModel.r, 0.0);
                float temperatureShape = max(radialModel.g, 0.0);
                float innerGate = smoothstep(1.8, 2.8, r);
                float outerGate = 1.0 - smoothstep(27.0, 30.0, r);
                float proxyEmissivity = pow(saturate(6.0 / r), 2.2) * innerGate * outerGate;
                float emissivity = lerp(proxyEmissivity, fluxShape, usePhysicalColor);
                float redshiftPower = usePhysicalColor > 0.5 ? 4.0 : max(_DiskGPower, 0.0);
                float observedWeight = emissivity * pow(g, redshiftPower) * _DiskBrightness * orderScale;
                float hotSpot = diskHotSpotWeight(disk, coverage);
                observedWeight += hotSpot * pow(g, redshiftPower) * _DiskHotSpotBrightness * orderScale;

                // Without LUT assets this is the original documented visual
                // proxy.  With LUT assets enabled, the baseline layer uses
                // normalized Page-Thorne F(r), T_obs = g T_emit, and bolometric
                // g^4 weighting.  Absolute luminosity still needs a separate
                // accretion-rate and mass normalization.
                // The hot spot uses (r_m, phi_m) from the transfer map; the
                // current Unity cube does not yet carry Delta t_m.
                float observedTemperature = g * max(_DiskTemperatureScale, 1.0) * max(temperatureShape, 1.0e-4);
                float3 baseDiskColor = usePhysicalColor > 0.5
                    ? sampleDiskColorLut(observedTemperature)
                    : blackbodyRamp(g);
                // Channel split, load-bearing: `.rgb` is the observed radiance
                // and carries F(r) g^p EXACTLY ONCE; `.a` is the producer's
                // sub-texel disk coverage times the display opacity knob and
                // nothing else. Every compositor below adds `rgb * a`, so
                // carrying observedWeight in both channels rendered
                // F(r)^2 g^(2p) - F^2 g^8 on the documented LUT path - and
                // squared _DiskBrightness and _DiskSecondaryScale with it.
                // generate_transfer_cubemap.py states the contract: "alpha is
                // disk-hit coverage in [0,1] ... consumers divide by
                // interpolated coverage and use coverage as opacity."
                float3 color = lerp(baseDiskColor, float3(1.0, 0.92, 0.62), saturate(hotSpot)) * observedWeight;
                float alpha = saturate(_DiskOpacity * coverage);
                return fixed4(color, alpha);
            }

            // One full-sky + disk shading pass for a keyframe sampler set.
            // Written as a macro because legacy CG sampler objects cannot be
            // passed as function arguments; the blend variant instantiates it
            // twice with independent bases and observer uniforms.
            #define GRBHXR_SHADE_SET(OUT_COLOR, WORLD_RAY, RIGHT, UP, FORWARD, EINF, EVENTC, ESCC, D0C, D1C, R0C, R1C) \
            { \
                float3 shadeLocalRay = worldDirectionToBasis(WORLD_RAY, RIGHT, UP, FORWARD); \
                float shadeObsFactor = observerFactor(shadeLocalRay, EINF); \
                float4 shadeCubeDir = texCUBE(ESCC, shadeLocalRay); \
                fixed4 shadeCubeEvent = texCUBE(EVENTC, shadeLocalRay); \
                float shadeCoverage = saturate(shadeCubeDir.a); \
                fixed4 shadeSky = fixed4(0.0, 0.0, 0.0, 1.0); \
                if (shadeCoverage > 1.0e-4) \
                { \
                    float3 shadeWorldDir = basisDirectionToWorld(shadeCubeDir.xyz, RIGHT, UP, FORWARD); \
                    if (_ProbeMode > 0.5) \
                    { \
                        shadeSky = protractorProbe(shadeWorldDir); \
                    } \
                    else \
                    { \
                        shadeSky = sampleSkybox(shadeWorldDir, _SkyboxLodBias); \
                        shadeSky.rgb = applySkyObserver(shadeSky.rgb, shadeObsFactor); \
                    } \
                    shadeSky = fixed4(shadeSky.rgb * shadeCoverage, 1.0); \
                } \
                else \
                { \
                    shadeSky = shadeCubeEvent; \
                } \
                OUT_COLOR = shadeSky; \
                if (_UseDiskTransfer > 0.5 && _DiskVisualMode > 0.5) \
                { \
                    float shadeCov1 = 0.0; \
                    float shadeCov0 = 0.0; \
                    float4 shadeDisk1 = unpackDiskSample( \
                        texCUBE(D1C, shadeLocalRay), texCUBE(R1C, shadeLocalRay), shadeCov1); \
                    float4 shadeDisk0 = unpackDiskSample( \
                        texCUBE(D0C, shadeLocalRay), texCUBE(R0C, shadeLocalRay), shadeCov0); \
                    fixed4 shadeLayer1 = diskVisualLayer(shadeDisk1, 1.0, shadeCov1, shadeObsFactor); \
                    fixed4 shadeLayer0 = diskVisualLayer(shadeDisk0, 0.0, shadeCov0, shadeObsFactor); \
                    float3 shadeRgb = OUT_COLOR.rgb; \
                    shadeRgb = saturate(shadeRgb + shadeLayer1.rgb * shadeLayer1.a); \
                    shadeRgb = saturate(shadeRgb + shadeLayer0.rgb * shadeLayer0.a); \
                    OUT_COLOR = fixed4(shadeRgb, OUT_COLOR.a); \
                } \
            }

            fixed4 compositeDiskVisual(fixed4 baseColor, float3 localRay)
            {
                if (_UseDiskTransfer <= 0.5 || _DiskVisualMode <= 0.5)
                {
                    return baseColor;
                }
                float obsFactor = observerFactor(localRay, _ObsEInf);
                float coverage1 = 0.0;
                float coverage0 = 0.0;
                float4 disk1 = unpackDiskSample(
                    texCUBE(_DiskOrder1Cube, localRay),
                    texCUBE(_DiskOrder1RedshiftCube, localRay),
                    coverage1
                );
                float4 disk0 = unpackDiskSample(
                    texCUBE(_DiskOrder0Cube, localRay),
                    texCUBE(_DiskOrder0RedshiftCube, localRay),
                    coverage0
                );
                fixed4 layer1 = diskVisualLayer(disk1, 1.0, coverage1, obsFactor);
                fixed4 layer0 = diskVisualLayer(disk0, 0.0, coverage0, obsFactor);
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
                #ifdef GRBHXR_ROAM_BLEND
                // Continuous roam: dissolve between two exact keyframe
                // solutions by the position-derived weight. Each set carries
                // its own basis (worldline azimuth) and observer uniforms.
                fixed4 blendColorA;
                GRBHXR_SHADE_SET(
                    blendColorA, worldRay,
                    _LensWorldRight.xyz, _LensWorldUp.xyz, _LensWorldForward.xyz,
                    _ObsEInf,
                    _EventCube, _EscapeDirCube,
                    _DiskOrder0Cube, _DiskOrder1Cube,
                    _DiskOrder0RedshiftCube, _DiskOrder1RedshiftCube
                );
                fixed4 blendColorB;
                GRBHXR_SHADE_SET(
                    blendColorB, worldRay,
                    _LensWorldRightB.xyz, _LensWorldUpB.xyz, _LensWorldForwardB.xyz,
                    _ObsEInfB,
                    _EventCubeB, _EscapeDirCubeB,
                    _DiskOrder0CubeB, _DiskOrder1CubeB,
                    _DiskOrder0RedshiftCubeB, _DiskOrder1RedshiftCubeB
                );
                return lerp(blendColorA, blendColorB, saturate(_RoamBlend));
                #else
                float alphaMin = _LensScreenBounds.x;
                float alphaMax = _LensScreenBounds.y;
                float betaMin = _LensScreenBounds.z;
                float betaMax = _LensScreenBounds.w;
                if (_UseDiskTransfer > 0.5 && _DiskAuditMode > 0.5)
                {
                    float coverage0 = 0.0;
                    float coverage1 = 0.0;
                    float4 disk0 = unpackDiskSample(
                        texCUBE(_DiskOrder0Cube, localRay),
                        texCUBE(_DiskOrder0RedshiftCube, localRay),
                        coverage0
                    );
                    float4 disk1 = unpackDiskSample(
                        texCUBE(_DiskOrder1Cube, localRay),
                        texCUBE(_DiskOrder1RedshiftCube, localRay),
                        coverage1
                    );
                    return _DiskAuditMode > 1.5
                        ? diskAuditColor(disk1, 1.0, coverage1)
                        : diskAuditColor(disk0, 0.0, coverage0);
                }

                fixed4 fullSkyColor = fixed4(0.0, 0.0, 0.0, 1.0);
                if (_UseFullSkyTransfer > 0.5)
                {
                    // Alpha is fractional escape coverage at the shadow limb
                    // (schema v3); direction channels are premultiplied by it.
                    // Blending sky against the event color by coverage
                    // anti-aliases the capture boundary; binary-alpha legacy
                    // cubes reduce to the old hard branch.
                    float4 cubeDir = texCUBE(_EscapeDirCube, localRay);
                    fixed4 cubeEvent = texCUBE(_EventCube, localRay);
                    float escapeCoverage = saturate(cubeDir.a);
                    if (escapeCoverage <= 1.0e-4)
                    {
                        fullSkyColor = cubeEvent;
                    }
                    else
                    {
                        float3 cubeWorldDir = lensDirectionToWorld(cubeDir.xyz);
                        fixed4 skyColor;
                        if (_ProbeMode > 0.5)
                        {
                            skyColor = protractorProbe(cubeWorldDir);
                        }
                        else
                        {
                            skyColor = sampleBackground(cubeWorldDir, worldRay, _SkyboxLodBias);
                            // Observer-side factor: gravitational blueshift for
                            // static frames (falls back to the scalar
                            // _SkyBlueshift when _ObsEInf is at its default),
                            // direction-dependent aberration/Doppler for the
                            // falling frame; chromatic shift + bolometric g^4.
                            float skyObsFactor = observerFactor(localRay, _ObsEInf) * max(_SkyBlueshift, 1.0e-3);
                            skyColor.rgb = applySkyObserver(skyColor.rgb, skyObsFactor);
                        }
                        // The non-escaping fraction of the texel is captured
                        // light: physically black. The event palette (escape
                        // renders blue) is audit-only and must not leak into
                        // the fractional limb blend.
                        fullSkyColor = fixed4(skyColor.rgb * escapeCoverage, 1.0);
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
                    fixed4 baseColor = _UseFullSkyTransfer > 0.5 ? fullSkyColor : sampleBackground(worldRay, worldRay, _SkyboxLodBias);
                    return compositeDiskVisual(baseColor, localRay);
                }

                #ifndef GRBHXR_ROAM_BLEND
                if (_UseLiveWindow > 0.5)
                {
                    // Live high-resolution window: the SAME exact solution as
                    // the full-sky cube (same observer position; the binder
                    // only displays a window whose pass origin matches the
                    // cube), sampled at near-headset angular density around
                    // the hole. Coverage in dir.a is fractional (limb-refine
                    // subrays), disk layers carry coverage-premultiplied
                    // means. The edge feather below blends two RESOLUTIONS of
                    // one solution, never two observer states.
                    float4 winDir = tex2D(_EscapeDirTex, lensUv);
                    float winCoverage = saturate(winDir.a);
                    fixed4 winColor = fixed4(0.0, 0.0, 0.0, 1.0);
                    if (winCoverage > 1.0e-4)
                    {
                        float3 winWorldDir = lensDirectionToWorld(winDir.xyz);
                        if (_ProbeMode > 0.5)
                        {
                            winColor = protractorProbe(winWorldDir);
                        }
                        else
                        {
                            fixed4 winSky = sampleBackground(winWorldDir, worldRay, _StrongLensLodBias);
                            float winObs = observerFactor(localRay, _ObsEInf) * max(_SkyBlueshift, 1.0e-3);
                            winSky.rgb = applySkyObserver(winSky.rgb, winObs);
                            winColor = fixed4(winSky.rgb * winCoverage, 1.0);
                        }
                    }
                    if (_UseDiskTransfer > 0.5 && _DiskVisualMode > 0.5)
                    {
                        float winObsFactor = observerFactor(localRay, _ObsEInf);
                        float winCov1 = 0.0;
                        float winCov0 = 0.0;
                        float4 winDisk1 = unpackDiskSample(
                            tex2D(_WindowDisk1Tex, lensUv), tex2D(_WindowRedshift1Tex, lensUv), winCov1);
                        float4 winDisk0 = unpackDiskSample(
                            tex2D(_WindowDisk0Tex, lensUv), tex2D(_WindowRedshift0Tex, lensUv), winCov0);
                        fixed4 winLayer1 = diskVisualLayer(winDisk1, 1.0, winCov1, winObsFactor);
                        fixed4 winLayer0 = diskVisualLayer(winDisk0, 0.0, winCov0, winObsFactor);
                        winColor.rgb = saturate(winColor.rgb + winLayer1.rgb * winLayer1.a);
                        winColor.rgb = saturate(winColor.rgb + winLayer0.rgb * winLayer0.a);
                    }
                    fixed4 cubeComposite = compositeDiskVisual(fullSkyColor, localRay);
                    float winEdgeDistance = min(min(lensUv.x, 1.0 - lensUv.x), min(lensUv.y, 1.0 - lensUv.y));
                    float windowWeight = smoothstep(0.0, 0.04, winEdgeDistance);
                    return lerp(cubeComposite, winColor, windowWeight);
                }
                #endif

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
                fixed4 localColor = sampleBackground(worldDir, worldRay, _StrongLensLodBias);
                if (_UseFullSkyTransfer > 0.5)
                {
                    float edgeDistance = min(min(lensUv.x, 1.0 - lensUv.x), min(lensUv.y, 1.0 - lensUv.y));
                    float localWeight = smoothstep(0.0, 0.04, edgeDistance);
                    return compositeDiskVisual(lerp(fullSkyColor, localColor, localWeight), localRay);
                }
                return compositeDiskVisual(localColor, localRay);
                #endif
            }
            ENDCG
        }
    }
}
