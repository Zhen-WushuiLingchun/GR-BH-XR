Shader "GR-BH-XR/Kerr Lens Static Preview"
{
    Properties
    {
        _EventTex ("Event Texture", 2D) = "black" {}
        _EscapeDirTex ("Escape Direction Texture", 2D) = "black" {}
        _SkyboxCubemap ("Skybox Cubemap", Cube) = "" {}
        _LensScreenBounds ("Lens Screen Bounds", Vector) = (-8, 8, -8, 8)
        _LensRObs ("Lens Observer Radius", Float) = 100
        _UseAngularWindow ("Use Angular Window", Float) = 0
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        Pass
        {
            Cull Off
            ZWrite On
            ZTest Always

            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            sampler2D _EventTex;
            sampler2D _EscapeDirTex;
            samplerCUBE _SkyboxCubemap;
            float4 _LensScreenBounds;
            float _LensRObs;
            float _UseAngularWindow;

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 worldPos : TEXCOORD1;
                float4 screenPos : TEXCOORD2;
            };

            v2f vert(appdata v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                o.worldPos = mul(unity_ObjectToWorld, v.vertex).xyz;
                o.screenPos = ComputeScreenPos(o.vertex);
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float3 worldRay = normalize(i.worldPos - _WorldSpaceCameraPos);
                float3 localRay = normalize(mul((float3x3)unity_WorldToObject, worldRay));
                float alphaMin = _LensScreenBounds.x;
                float alphaMax = _LensScreenBounds.y;
                float betaMin = _LensScreenBounds.z;
                float betaMax = _LensScreenBounds.w;

                float2 lensUv = i.uv;
                bool insideAngularWindow = false;
                if (_UseAngularWindow > 0.5)
                {
                    float localForward = abs(localRay.z);
                    if (localForward > 1.0e-5)
                    {
                        float alpha = _LensRObs * localRay.x / localForward;
                        float beta = -_LensRObs * localRay.y / localForward;
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
                    return texCUBE(_SkyboxCubemap, worldRay);
                }

                float4 dir = tex2D(_EscapeDirTex, lensUv);
                fixed4 eventColor = tex2D(_EventTex, lensUv);
                if (dir.a < 0.5)
                {
                    return eventColor;
                }
                float3 worldDir = normalize(mul((float3x3)unity_ObjectToWorld, dir.xyz));
                return texCUBE(_SkyboxCubemap, worldDir);
            }
            ENDCG
        }
    }
}
