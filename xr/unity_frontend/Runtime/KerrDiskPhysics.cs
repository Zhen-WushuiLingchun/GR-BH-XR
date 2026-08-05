using System;
using UnityEngine;

namespace GRBHXR
{
    /// <summary>
    /// C# port of the audited Python disk physics (src/gr_bh_xr/disk_spectrum.py)
    /// needed for LIVE mass/spin adjustment: BPT ISCO, Keplerian angular
    /// velocity, and the Page-Thorne flux closed form (root/log expression).
    /// Convention matches the live tracer's DiskOmega: the disk co-rotates
    /// with the spin (orbit sign = sign(a)), so a negative spin is the exact
    /// mirror system - beaming side, ISCO, shadow asymmetry, and frame
    /// dragging all flip together, which is the falsification test that the
    /// rendering is first-principles and not painted.
    /// </summary>
    internal static class KerrDiskPhysics
    {
        /// <summary>BPT ISCO for the co-rotating disk (symmetric in a -> -a).</summary>
        public static double IscoRadius(double mass, double spin)
        {
            double a = Math.Abs(spin) / mass;
            double z1 = 1.0 + Math.Pow(1.0 - a * a, 1.0 / 3.0)
                * (Math.Pow(1.0 + a, 1.0 / 3.0) + Math.Pow(1.0 - a, 1.0 / 3.0));
            double z2 = Math.Sqrt(3.0 * a * a + z1 * z1);
            return mass * (3.0 + z2 - Math.Sqrt((3.0 - z1) * (3.0 + z1 + 2.0 * z2)));
        }

        /// <summary>Keplerian Omega of the co-rotating disk, sign following
        /// the spin (matches the compute tracer's DiskOmega).</summary>
        public static double KeplerianOmega(double mass, double spin, double r)
        {
            double orbitSign = spin < 0.0 ? -1.0 : 1.0;
            double sqrtM = Math.Sqrt(mass);
            return orbitSign * sqrtM / (Math.Pow(r, 1.5) + orbitSign * spin * sqrtM);
        }

        /// <summary>Page-Thorne flux shape via the root/log closed form
        /// (disk_spectrum.page_thorne_flux_shape_closed_form). Uses the
        /// magnitude of the spin: the co-rotating disk sees the prograde
        /// flux profile regardless of spin sign.</summary>
        public static double PageThorneFluxShape(double mass, double spin, double r, double rIsco)
        {
            if (r <= rIsco)
            {
                return 0.0;
            }
            // The closed form is singular exactly at a = 0; clamp to a tiny
            // prograde spin (relative error at 1e-3 is far below display
            // precision).
            double a = Math.Max(Math.Abs(spin) / mass, 1.0e-3);
            double x = Math.Sqrt(r / mass);
            double x0 = Math.Sqrt(rIsco / mass);
            double angle = Math.Acos(Math.Max(-1.0, Math.Min(1.0, -a))) / 3.0;
            double[] roots =
            {
                2.0 * Math.Cos(angle - 2.0 * Math.PI / 3.0),
                2.0 * Math.Cos(angle + 2.0 * Math.PI / 3.0),
                2.0 * Math.Cos(angle),
            };
            Array.Sort(roots);
            double bracket = x - x0 - 1.5 * a * Math.Log(x / x0);
            for (int index = 0; index < 3; index += 1)
            {
                double root = roots[index];
                double other0 = roots[(index + 1) % 3];
                double other1 = roots[(index + 2) % 3];
                double coefficient = (root - a) * (root - a)
                    / (root * (root - other0) * (root - other1));
                bracket -= 3.0 * coefficient * Math.Log((x - root) / (x0 - root));
            }
            double denominator = Math.Pow(x, 4.0) * (x * x * x - 3.0 * x + 2.0 * a);
            if (denominator <= 0.0 || double.IsNaN(bracket) || double.IsInfinity(bracket))
            {
                return 0.0;
            }
            return Math.Max(0.0, 1.5 * bracket / (mass * mass * denominator));
        }

        /// <summary>Regenerate the radial LUT texture rows (F_norm, T_shape)
        /// used by the disk shader, for the CURRENT mass and spin. Returns
        /// the sample array (RGBA per texel) and the inner radius.</summary>
        public static Color[] BuildRadialLut(double mass, double spin, double rOut, int samples, out double rIsco)
        {
            rIsco = IscoRadius(mass, spin);
            var flux = new double[samples];
            double peak = 0.0;
            for (int i = 0; i < samples; i += 1)
            {
                double r = rIsco + (rOut - rIsco) * i / (samples - 1.0);
                flux[i] = PageThorneFluxShape(mass, spin, r, rIsco);
                peak = Math.Max(peak, flux[i]);
            }
            var rows = new Color[samples];
            for (int i = 0; i < samples; i += 1)
            {
                float f = peak > 0.0 ? (float)(flux[i] / peak) : 0.0f;
                float t = f > 0.0f ? Mathf.Pow(f, 0.25f) : 0.0f;
                rows[i] = new Color(f, t, 0.0f, 1.0f);
            }
            return rows;
        }
    }
}
