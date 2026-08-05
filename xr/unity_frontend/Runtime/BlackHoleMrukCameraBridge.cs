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
            public long deliveredFrames;
            public DateTime timestamp;
        }

        private const string AccessTypeName = "Meta.XR.PassthroughCameraAccess";
        // Assembly-qualified fast path. MRUK 85.0.0 compiles
        // Core/Scripts/PassthroughCameraAccess.cs into meta.xr.mrutilitykit,
        // whose asmdef has empty includePlatforms and no defineConstraints, so
        // no platform or define can suppress it. Resolving by name first
        // removes the dependency on the type happening to be reachable through
        // an AppDomain walk in a built player.
        private const string AccessTypeQualifiedName =
            "Meta.XR.PassthroughCameraAccess, meta.xr.mrutilitykit";

        private Type accessType;
        private GameObject host;
        private Component access;
        private PropertyInfo isPlayingProperty;
        private PropertyInfo isUpdatedProperty;
        private PropertyInfo currentResolutionProperty;
        private PropertyInfo intrinsicsProperty;
        private PropertyInfo timestampProperty;
        private MethodInfo getTextureMethod;
        private MethodInfo getCameraPoseMethod;
        private string lastError = "not started";
        private static string resolvedVia = "unresolved";

        // Delivered-frame evidence. `IsPlaying` plus an allocated texture at
        // the requested resolution proves an allocation, not a photon: it is
        // the same failure class as the 16-px WebCamTexture placeholder one
        // level up. MRUK publishes a real monotonic clock (Timestamp, written
        // in the same block that stamps the update frame), so counting
        // distinct timestamps is order-independent evidence of delivery,
        // unlike a boolean latch on IsUpdatedThisFrame which depends on
        // script execution order.
        private bool hasEverUpdated;
        private long deliveredFrames;
        private int distinctTimestamps;
        private DateTime lastTimestamp = DateTime.MinValue;
        private float lastDeliveryRealtime = -1.0f;

        /// <summary>
        /// Distinct MRUK timestamps required before the calibrated-delivery
        /// acceptance line may be emitted.
        ///
        /// N = 1 proves one buffer was filled once, which a single-shot or
        /// frozen feed satisfies forever after. N = 2 gives a single delta,
        /// and the FIRST delivery is a startup artifact (MRUK flips its
        /// playing latch on that very frame). N = 3 gives two independent
        /// inter-frame deltas, which is the smallest count that can show the
        /// stream is advancing rather than that it advanced once.
        ///
        /// MRUK's Timestamp is microseconds since the Unix epoch, so distinct
        /// comparison is exact with no float rounding. MaxFramerate is a
        /// CEILING, not a guarantee - MRUK documents that the actual rate
        /// varies with lighting and workload - so this count is deliberately
        /// small enough to hold at a degraded rate.
        /// </summary>
        public const int RequiredDistinctTimestamps = 3;

        /// <summary>
        /// Seconds without a NEW distinct timestamp, after acceptance, before
        /// the stream is reported stale. At the 30 fps we request the nominal
        /// period is 33 ms, so this is a ~60x margin and will not trip on a
        /// legitimate dip; even a pathological sustained 5 fps leaves a 10x
        /// margin. Short enough that a frozen passthrough plate is caught
        /// within a capture rather than after it.
        ///
        /// Measured as time since the timestamp last CHANGED, not as absolute
        /// age. Over Link the timestamp is the headset's realtime clock and
        /// its synchronisation with the host clock is unverified, so an
        /// absolute-age test could report a permanent false stall.
        /// </summary>
        public const float StaleAfterSeconds = 2.0f;

        public bool IsRunning => access != null;
        public string LastError => lastError;
        public bool HasEverUpdated => hasEverUpdated;
        public long DeliveredFrames => deliveredFrames;
        public int DistinctTimestamps => distinctTimestamps;
        public DateTime LastTimestamp => lastTimestamp;
        public static string ResolvedVia => resolvedVia;

        /// <summary>
        /// Delivery is accepted only after several DISTINCT timestamps.
        /// `IsPlaying` plus an allocated texture proves an allocation; one
        /// timestamp transition proves one fill; only repeated transitions
        /// prove a stream.
        /// </summary>
        public bool HasDeliveredStream => distinctTimestamps >= RequiredDistinctTimestamps;

        /// <summary>Seconds since the last distinct timestamp, or -1.</summary>
        public float DeliveryAgeSeconds =>
            lastDeliveryRealtime < 0.0f ? -1.0f : Time.realtimeSinceStartup - lastDeliveryRealtime;

        /// <summary>True once delivery has succeeded and then stopped.</summary>
        public bool IsStreamStale =>
            HasDeliveredStream && DeliveryAgeSeconds > StaleAfterSeconds;

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
            // Delivery evidence is PER SESSION. Without this reset a bridge
            // that saw one genuine frame in an earlier attempt would satisfy
            // HasEverUpdated immediately on restart, and an
            // allocated-but-stalled camera would emit the calibrated-delivery
            // acceptance line without a single new timestamp.
            ResetDeliveryEvidence();
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
                // Count distinct timestamps, not IsUpdatedThisFrame ticks.
                // PassthroughCameraAccess runs at [DefaultExecutionOrder(-100)]
                // and this component at 0, so the boolean happens to be
                // readable - but that is an accident of ordering, not a
                // contract. A changed timestamp is unambiguous delivery.
                DateTime timestamp = (DateTime)timestampProperty.GetValue(access);
                if (timestamp != lastTimestamp && timestamp != default)
                {
                    lastTimestamp = timestamp;
                    lastDeliveryRealtime = Time.realtimeSinceStartup;
                    deliveredFrames += 1;
                    hasEverUpdated = true;
                    if (distinctTimestamps < int.MaxValue)
                    {
                        distinctTimestamps += 1;
                    }
                }
                frame = new Frame
                {
                    texture = texture,
                    pose = pose,
                    resolution = resolution,
                    projection = projection,
                    updatedThisFrame = updated,
                    deliveredFrames = deliveredFrames,
                    timestamp = timestamp,
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
                // Destroy is deferred to end-of-frame, so a replacement bridge
                // could otherwise create a second PassthroughCameraAccess host
                // while this one is still active and driving the camera.
                // Disable the component and deactivate the host FIRST, so the
                // old feed is released in this frame rather than the next.
                if (access is Behaviour behaviour)
                {
                    behaviour.enabled = false;
                }
                host.SetActive(false);
                UnityEngine.Object.Destroy(host);
            }
            host = null;
            access = null;
            accessType = null;
            ResetDeliveryEvidence();
        }

        /// <summary>
        /// Clear every per-session delivery fact. Called on both the start and
        /// stop edges so frame evidence can never cross a session boundary.
        /// </summary>
        private void ResetDeliveryEvidence()
        {
            hasEverUpdated = false;
            deliveredFrames = 0;
            distinctTimestamps = 0;
            lastTimestamp = DateTime.MinValue;
            lastDeliveryRealtime = -1.0f;
        }

        private void CacheMembers()
        {
            const BindingFlags flags = BindingFlags.Instance | BindingFlags.Public;
            isPlayingProperty = RequireProperty("IsPlaying", flags);
            isUpdatedProperty = RequireProperty("IsUpdatedThisFrame", flags);
            currentResolutionProperty = RequireProperty("CurrentResolution", flags);
            intrinsicsProperty = RequireProperty("Intrinsics", flags);
            timestampProperty = RequireProperty("Timestamp", flags);
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

        /// <summary>
        /// Resolve the MRUK camera type without a compile-time reference.
        /// The assembly-qualified lookup is tried FIRST: an AppDomain walk
        /// only sees assemblies that are already loaded, and nothing in this
        /// package statically references MRUK, so relying on the walk alone
        /// makes discovery depend on load order. Type.GetType with an
        /// assembly-qualified name asks the runtime to load it. The scan is
        /// kept as a fallback for a renamed or repackaged assembly, and the
        /// route that succeeded is recorded so the player log distinguishes
        /// "not installed" from "installed but not reachable the fast way".
        /// </summary>
        private static Type FindAccessType()
        {
            Type qualified = Type.GetType(AccessTypeQualifiedName, false);
            if (qualified != null)
            {
                resolvedVia = "Type.GetType(assembly-qualified)";
                return qualified;
            }

            foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                Type type = assembly.GetType(AccessTypeName, false);
                if (type != null)
                {
                    resolvedVia = $"AppDomain scan ({assembly.GetName().Name})";
                    return type;
                }
            }
            resolvedVia = "unresolved";
            return null;
        }

        /// <summary>
        /// One formatted line carrying everything validation_targets.md
        /// demands of the gate record: backend, delivered resolution, focal
        /// length, principal point, sensor resolution, the derived projection,
        /// the pose with its source, and the lens offset. All of this was
        /// previously computed and discarded into a Vector4, so even a fully
        /// successful device run could not close the documented gate.
        ///
        /// LensOffset is included deliberately. MRUK ships a mock camera
        /// backend (PcaCameraMock) and leaves disablePcaMockFallback at its
        /// default, so a mock feed would satisfy IsPlaying, a non-null
        /// texture, parseable intrinsics AND a ticking timestamp. A
        /// degenerate lens offset is one of the few things a mock is unlikely
        /// to reproduce, so it belongs in the accepted evidence.
        /// </summary>
        public string DescribeCalibration()
        {
            if (access == null)
            {
                return "no MRUK camera bound";
            }
            try
            {
                Vector2Int resolution = (Vector2Int)currentResolutionProperty.GetValue(access);
                object intrinsics = intrinsicsProperty.GetValue(access);
                if (intrinsics == null)
                {
                    return $"current={resolution.x}x{resolution.y} intrinsics=NULL (calibration unavailable)";
                }
                Type intrinsicsType = intrinsics.GetType();
                object focal = intrinsicsType.GetField("FocalLength")?.GetValue(intrinsics);
                object principal = intrinsicsType.GetField("PrincipalPoint")?.GetValue(intrinsics);
                object sensor = intrinsicsType.GetField("SensorResolution")?.GetValue(intrinsics);
                object lensOffset = intrinsicsType.GetField("LensOffset")?.GetValue(intrinsics);
                Vector4 projection = ProjectionFromIntrinsics(intrinsics, resolution);
                Pose pose = (Pose)getCameraPoseMethod.Invoke(access, null);
                return
                    $"backend=Meta MRUK PassthroughCameraAccess route={resolvedVia} " +
                    $"current={resolution.x}x{resolution.y} sensor={sensor} " +
                    $"focal={focal} principal={principal} lensOffset={lensOffset} " +
                    $"proj=(sx {projection.x:R}, sy {projection.y:R}, ox {projection.z:R}, oy {projection.w:R}) " +
                    $"poseSource=GetCameraPose@Timestamp pos={pose.position:F4} rot={pose.rotation:F4} " +
                    $"frames={deliveredFrames} lastTimestamp={lastTimestamp:O}";
            }
            catch (Exception ex)
            {
                return $"calibration read failed: {Unwrap(ex).Message}";
            }
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
                // The delivered-frame latch depends on this, so an MRUK
                // version that drops it must fail the editor contract gate
                // rather than silently reverting acceptance to "IsPlaying".
                "Timestamp",
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
