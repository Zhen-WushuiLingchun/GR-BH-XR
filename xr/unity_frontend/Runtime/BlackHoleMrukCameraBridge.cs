using System;
using System.Reflection;
using UnityEngine;

namespace GRBHXR
{
    /// <summary>
    /// Late-bound adapter for Meta's supported MRUK PassthroughCameraAccess.
    /// The core renderer remains usable without Meta packages; when MRUK is
    /// installed, this bridge consumes its timestamped texture, calibrated
    /// intrinsics, and camera pose instead of the legacy Windows virtual
    /// camera fallback.
    /// </summary>
    internal sealed class BlackHoleMrukCameraBridge
    {
        internal struct Frame
        {
            public Texture texture;
            public Pose pose;
            public Vector2Int resolution;
            // u = projection.z + projection.x * (x / z)
            // v = projection.w + projection.y * (y / z)
            public Vector4 projection;
            public bool updatedThisFrame;
        }

        private const string AccessTypeName = "Meta.XR.PassthroughCameraAccess";

        private Type accessType;
        private GameObject host;
        private Component access;
        private PropertyInfo isPlayingProperty;
        private PropertyInfo isUpdatedProperty;
        private PropertyInfo currentResolutionProperty;
        private PropertyInfo intrinsicsProperty;
        private MethodInfo getTextureMethod;
        private MethodInfo getCameraPoseMethod;
        private string lastError = "not started";

        public bool IsRunning => access != null;
        public string LastError => lastError;

        public static bool IsAvailable(out string reason)
        {
            Type type = FindAccessType();
            if (type == null)
            {
                reason = "Meta MRUK PassthroughCameraAccess is not installed";
                return false;
            }

            try
            {
                ValidateContract(type);
                reason = $"{type.FullName} from {type.Assembly.GetName().Name}";
                return true;
            }
            catch (Exception ex)
            {
                reason = $"{type.FullName} contract mismatch: {Unwrap(ex).Message}";
                return false;
            }
        }

        public bool Start(Transform parent, int width, int height, int fps)
        {
            Stop();
            accessType = FindAccessType();
            if (accessType == null)
            {
                lastError = "Meta MRUK PassthroughCameraAccess type was not found";
                return false;
            }

            try
            {
                CacheMembers();
                host = new GameObject("GRBHXR Meta Passthrough Camera");
                host.SetActive(false);
                if (parent != null)
                {
                    host.transform.SetParent(parent, false);
                }

                access = host.AddComponent(accessType);
                Behaviour behaviour = access as Behaviour;
                if (behaviour != null)
                {
                    // Meta requires MaxFramerate to be assigned while the
                    // PassthroughCameraAccess component itself is disabled.
                    behaviour.enabled = false;
                }
                SetPublicField("CameraPosition", "Left");
                SetPublicField("RequestedResolution", new Vector2Int(width, height));
                PropertyInfo maxFramerate = accessType.GetProperty(
                    "MaxFramerate",
                    BindingFlags.Instance | BindingFlags.Public
                );
                maxFramerate?.SetValue(access, Mathf.Max(fps, 1));
                if (behaviour != null)
                {
                    behaviour.enabled = true;
                }
                host.SetActive(true);
                lastError = "waiting for the first MRUK frame";
                return true;
            }
            catch (Exception ex)
            {
                lastError = Unwrap(ex).Message;
                Stop();
                return false;
            }
        }

        public bool TryGetFrame(out Frame frame)
        {
            frame = default;
            if (access == null)
            {
                return false;
            }

            try
            {
                bool isPlaying = (bool)isPlayingProperty.GetValue(access);
                if (!isPlaying)
                {
                    Behaviour behaviour = access as Behaviour;
                    if (behaviour != null && !behaviour.enabled)
                    {
                        lastError = "MRUK disabled PassthroughCameraAccess after CameraPlay failed";
                    }
                    return false;
                }

                Texture texture = getTextureMethod.Invoke(access, null) as Texture;
                Vector2Int resolution = (Vector2Int)currentResolutionProperty.GetValue(access);
                if (texture == null || resolution.x <= 16 || resolution.y <= 16)
                {
                    lastError = "MRUK reports playing but has no usable texture";
                    return false;
                }

                Pose pose = (Pose)getCameraPoseMethod.Invoke(access, null);
                object intrinsics = intrinsicsProperty.GetValue(access);
                Vector4 projection = ProjectionFromIntrinsics(intrinsics, resolution);
                bool updated = (bool)isUpdatedProperty.GetValue(access);
                frame = new Frame
                {
                    texture = texture,
                    pose = pose,
                    resolution = resolution,
                    projection = projection,
                    updatedThisFrame = updated,
                };
                lastError = string.Empty;
                return true;
            }
            catch (Exception ex)
            {
                lastError = Unwrap(ex).Message;
                return false;
            }
        }

        public void Stop()
        {
            if (host != null)
            {
                UnityEngine.Object.Destroy(host);
            }
            host = null;
            access = null;
            accessType = null;
        }

        private void CacheMembers()
        {
            const BindingFlags flags = BindingFlags.Instance | BindingFlags.Public;
            isPlayingProperty = RequireProperty("IsPlaying", flags);
            isUpdatedProperty = RequireProperty("IsUpdatedThisFrame", flags);
            currentResolutionProperty = RequireProperty("CurrentResolution", flags);
            intrinsicsProperty = RequireProperty("Intrinsics", flags);
            getTextureMethod = RequireMethod("GetTexture", flags);
            getCameraPoseMethod = RequireMethod("GetCameraPose", flags);
        }

        private PropertyInfo RequireProperty(string name, BindingFlags flags)
        {
            return accessType.GetProperty(name, flags)
                ?? throw new MissingMemberException(accessType.FullName, name);
        }

        private MethodInfo RequireMethod(string name, BindingFlags flags)
        {
            return accessType.GetMethod(name, flags)
                ?? throw new MissingMethodException(accessType.FullName, name);
        }

        private void SetPublicField(string name, object value)
        {
            FieldInfo field = accessType.GetField(name, BindingFlags.Instance | BindingFlags.Public)
                ?? throw new MissingFieldException(accessType.FullName, name);
            if (field.FieldType.IsEnum && value is string enumName)
            {
                value = Enum.Parse(field.FieldType, enumName);
            }
            field.SetValue(access, value);
        }

        private static Vector4 ProjectionFromIntrinsics(object intrinsics, Vector2Int resolution)
        {
            if (intrinsics == null)
            {
                throw new InvalidOperationException("MRUK returned null camera intrinsics");
            }

            Type type = intrinsics.GetType();
            Vector2 focal = ReadField<Vector2>(type, intrinsics, "FocalLength");
            Vector2 principal = ReadField<Vector2>(type, intrinsics, "PrincipalPoint");
            Vector2Int sensor = ReadField<Vector2Int>(type, intrinsics, "SensorResolution");
            if (focal.x <= 0.0f || focal.y <= 0.0f || sensor.x <= 0 || sensor.y <= 0)
            {
                throw new InvalidOperationException("MRUK returned invalid camera calibration");
            }

            Vector2 scale = new Vector2(
                (float)resolution.x / sensor.x,
                (float)resolution.y / sensor.y
            );
            scale /= Mathf.Max(scale.x, scale.y);
            float cropX = sensor.x * (1.0f - scale.x) * 0.5f;
            float cropY = sensor.y * (1.0f - scale.y) * 0.5f;
            float cropWidth = sensor.x * scale.x;
            float cropHeight = sensor.y * scale.y;
            return new Vector4(
                focal.x / cropWidth,
                focal.y / cropHeight,
                (principal.x - cropX) / cropWidth,
                (principal.y - cropY) / cropHeight
            );
        }

        private static T ReadField<T>(Type type, object instance, string name)
        {
            FieldInfo field = type.GetField(name, BindingFlags.Instance | BindingFlags.Public)
                ?? throw new MissingFieldException(type.FullName, name);
            return (T)field.GetValue(instance);
        }

        private static Type FindAccessType()
        {
            foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                Type type = assembly.GetType(AccessTypeName, false);
                if (type != null)
                {
                    return type;
                }
            }
            return null;
        }

        private static void ValidateContract(Type type)
        {
            const BindingFlags flags = BindingFlags.Instance | BindingFlags.Public;
            if (!typeof(Component).IsAssignableFrom(type))
            {
                throw new InvalidOperationException($"{type.FullName} is not a Unity Component");
            }

            foreach (string propertyName in new[]
            {
                "IsPlaying",
                "IsUpdatedThisFrame",
                "CurrentResolution",
                "Intrinsics",
                "MaxFramerate",
            })
            {
                if (type.GetProperty(propertyName, flags) == null)
                {
                    throw new MissingMemberException(type.FullName, propertyName);
                }
            }

            foreach (string fieldName in new[] { "CameraPosition", "RequestedResolution" })
            {
                if (type.GetField(fieldName, flags) == null)
                {
                    throw new MissingFieldException(type.FullName, fieldName);
                }
            }

            foreach (string methodName in new[] { "GetTexture", "GetCameraPose" })
            {
                if (type.GetMethod(methodName, flags) == null)
                {
                    throw new MissingMethodException(type.FullName, methodName);
                }
            }
        }

        private static Exception Unwrap(Exception ex)
        {
            return ex is TargetInvocationException invocation && invocation.InnerException != null
                ? invocation.InnerException
                : ex;
        }
    }
}
