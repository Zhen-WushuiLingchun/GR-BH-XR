using UnityEngine;

namespace GRBHXR
{
    /// <summary>
    /// Pure math for the observer-position-dependent map basis.
    ///
    /// Kerr is stationary and axisymmetric, so a full-sky transfer map traced
    /// at (r, theta, phi = 0) serves every azimuth: moving the observer to
    /// azimuth phi rigidly rotates the whole solution about the spin axis.
    /// This class reproduces the Python `unity_basis_from_inclination`
    /// convention (BH frame: +Z spin axis, observer at phi = 0; map local
    /// frame: +z toward the black hole, +y the spin-axis projection) and
    /// converts observer (theta, phi) into world-space basis vectors relative
    /// to a reference row where the lens anchor was calibrated.
    /// </summary>
    public static class KerrObserverBasis
    {
        public struct BhBasis
        {
            public Vector3 Right;
            public Vector3 Up;
            public Vector3 Forward;
        }

        /// <summary>BH-frame basis of the traced map row at observer polar angle theta.</summary>
        public static BhBasis RowBasis(float thetaDeg)
        {
            float theta = thetaDeg * Mathf.Deg2Rad;
            var observer = new Vector3(Mathf.Sin(theta), 0.0f, Mathf.Cos(theta));
            Vector3 forward = -observer;
            var spin = new Vector3(0.0f, 0.0f, 1.0f);
            Vector3 up = spin - Vector3.Dot(spin, forward) * forward;
            if (up.sqrMagnitude < 1.0e-10f)
            {
                var fallback = new Vector3(1.0f, 0.0f, 0.0f);
                up = fallback - Vector3.Dot(fallback, forward) * forward;
            }
            up = up.normalized;
            Vector3 right = Vector3.Cross(up, forward).normalized;
            up = Vector3.Cross(forward, right);
            return new BhBasis { Right = right, Up = up, Forward = forward };
        }

        /// <summary>Rotate a BH-frame vector by azimuth about the spin axis (+phi prograde).</summary>
        public static Vector3 RotateAboutSpin(Vector3 bhVector, float azimuthDeg)
        {
            float azimuth = azimuthDeg * Mathf.Deg2Rad;
            float cos = Mathf.Cos(azimuth);
            float sin = Mathf.Sin(azimuth);
            return new Vector3(
                bhVector.x * cos - bhVector.y * sin,
                bhVector.x * sin + bhVector.y * cos,
                bhVector.z
            );
        }

        /// <summary>Express a BH-frame vector in the reference row's local map components.</summary>
        public static Vector3 BhToReferenceLocal(Vector3 bhVector, BhBasis reference)
        {
            return new Vector3(
                Vector3.Dot(bhVector, reference.Right),
                Vector3.Dot(bhVector, reference.Up),
                Vector3.Dot(bhVector, reference.Forward)
            );
        }

        /// <summary>
        /// World-space map basis for an observer at (thetaDeg, azimuthDeg), given
        /// the anchor rotation calibrated while the observer sat at the
        /// reference row (thetaRefDeg, azimuth 0).
        /// </summary>
        public static void WorldBasis(
            Quaternion anchorRotation,
            float thetaRefDeg,
            float thetaDeg,
            float azimuthDeg,
            out Vector3 worldRight,
            out Vector3 worldUp,
            out Vector3 worldForward
        )
        {
            BhBasis reference = RowBasis(thetaRefDeg);
            BhBasis row = RowBasis(thetaDeg);
            worldRight = anchorRotation * BhToReferenceLocal(RotateAboutSpin(row.Right, azimuthDeg), reference);
            worldUp = anchorRotation * BhToReferenceLocal(RotateAboutSpin(row.Up, azimuthDeg), reference);
            worldForward = anchorRotation * BhToReferenceLocal(RotateAboutSpin(row.Forward, azimuthDeg), reference);
        }

        /// <summary>
        /// World-space spherical walking directions at the observer position:
        /// outward radial, +theta (southward), +phi (prograde).
        /// </summary>
        public static void SphericalDirections(
            Quaternion anchorRotation,
            float thetaRefDeg,
            float thetaDeg,
            float azimuthDeg,
            out Vector3 radialOutward,
            out Vector3 polarSouth,
            out Vector3 azimuthPrograde
        )
        {
            BhBasis reference = RowBasis(thetaRefDeg);
            float theta = thetaDeg * Mathf.Deg2Rad;
            // BH-frame unit vectors at azimuth 0, then rotated by azimuth.
            var radialBh = new Vector3(Mathf.Sin(theta), 0.0f, Mathf.Cos(theta));
            var polarBh = new Vector3(Mathf.Cos(theta), 0.0f, -Mathf.Sin(theta));
            var azimuthBh = new Vector3(0.0f, 1.0f, 0.0f);
            radialOutward = anchorRotation * BhToReferenceLocal(RotateAboutSpin(radialBh, azimuthDeg), reference);
            polarSouth = anchorRotation * BhToReferenceLocal(RotateAboutSpin(polarBh, azimuthDeg), reference);
            azimuthPrograde = anchorRotation * BhToReferenceLocal(RotateAboutSpin(azimuthBh, azimuthDeg), reference);
        }
    }
}
