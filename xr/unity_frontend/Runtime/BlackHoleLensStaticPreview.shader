Shader "GR-BH-XR/Kerr Lens Static Preview"
{
    Properties
    {
        _EventTex ("Event Texture", 2D) = "black" {}
        _EscapeDirTex ("Escape Direction Texture", 2D) = "black" {}
        _SkyboxCubemap ("Skybox Cubemap", Cube) = "" {}
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            sampler2D _EventTex;
            sampler2D _EscapeDirTex;
            samplerCUBE _SkyboxCubemap;

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
                float2 uv : TEXCOORD0;
            };

            v2f vert(appdata v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float4 dir = tex2D(_EscapeDirTex, i.uv);
                fixed4 eventColor = tex2D(_EventTex, i.uv);
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
