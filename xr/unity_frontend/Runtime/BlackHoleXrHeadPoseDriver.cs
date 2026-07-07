using UnityEngine;
using UnityEngine.XR;

namespace GRBHXR
{
    [DefaultExecutionOrder(-10000)]
    public sealed class BlackHoleXrHeadPoseDriver : MonoBehaviour
    {
        [SerializeField] private bool enableInPlayMode = true;
        [SerializeField] private Transform trackingOrigin;
        [SerializeField] private Vector3 fallbackLocalPosition;
        [SerializeField] private Vector3 lastHeadLocalPosition;
        [SerializeField] private Quaternion lastHeadLocalRotation = Quaternion.identity;
        [SerializeField] private bool poseValid;

        public bool PoseValid => poseValid;
        public Vector3 LastHeadLocalPosition => lastHeadLocalPosition;
        public Quaternion LastHeadLocalRotation => lastHeadLocalRotation;

        private void Awake()
        {
            fallbackLocalPosition = transform.localPosition;
        }

        private void LateUpdate()
        {
            if (!enableInPlayMode || !Application.isPlaying)
            {
                return;
            }

            poseValid = TryReadHeadPose(out Vector3 localPosition, out Quaternion localRotation);
            if (!poseValid)
            {
                localPosition = fallbackLocalPosition;
                localRotation = Quaternion.identity;
            }

            lastHeadLocalPosition = localPosition;
            lastHeadLocalRotation = localRotation;

            if (trackingOrigin != null)
            {
                transform.SetPositionAndRotation(
                    trackingOrigin.TransformPoint(localPosition),
                    trackingOrigin.rotation * localRotation
                );
            }
            else
            {
                transform.localPosition = localPosition;
                transform.localRotation = localRotation;
            }
        }

        private static bool TryReadHeadPose(out Vector3 localPosition, out Quaternion localRotation)
        {
            InputDevice head = InputDevices.GetDeviceAtXRNode(XRNode.Head);
            bool hasPosition = head.TryGetFeatureValue(CommonUsages.devicePosition, out localPosition);
            bool hasRotation = head.TryGetFeatureValue(CommonUsages.deviceRotation, out localRotation);

            if (!hasPosition)
            {
                localPosition = InputTracking.GetLocalPosition(XRNode.Head);
                hasPosition = localPosition.sqrMagnitude > 0.0f;
            }
            if (!hasRotation)
            {
                localRotation = InputTracking.GetLocalRotation(XRNode.Head);
                hasRotation = localRotation != default;
            }

            if (!hasPosition)
            {
                localPosition = Vector3.zero;
            }
            if (!hasRotation)
            {
                localRotation = Quaternion.identity;
            }

            return hasPosition || hasRotation;
        }
    }
}
