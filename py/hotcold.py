"""
This file is part of the StellarClocks project.
Copyright 2014 David W. Hogg (NYU).
"""

import numpy as np
import matplotlib.pylab as plt
import emcee
import triangle

def trapezoid(times, period, offset, depth, duration, gress):
    fractions = np.zeros_like(times)
    ts = np.mod((times - offset), period)
    ts[ts > 0.5 * period] -= period
    ts = np.abs(ts)
    inside = ts < 0.5 * (duration + gress)
    fractions[inside] = (depth / gress) * (0.5 * (duration + gress) - ts[inside])
    fractions[ts < 0.5 * (duration - gress)] = depth
    return fractions

def get_fractions(times, period, offset, depth, duration, gress):
    return trapezoid(times, period, offset, depth, duration, gress)

def distort_times(times, period, Aamp, Bamp):
    thetas = 2 * np.pi * times / period
    return times - Aamp * np.cos(thetas) - Bamp * np.cos(thetas)

def integrate_fractions(times, exptime, hotperiod, offset, depth, duration, gress, coldperiod, Aamp, Bamp, K):
    delta_times = np.arange(-0.5 * exptime + 0.5 * exptime / K, 0.5 * exptime, exptime / K)
    bigtimes = times[:, None] + delta_times[None, :]
    bigtimes = distort_times(bigtimes, coldperiod, Aamp, Bamp)
    bigfracs = get_fractions(bigtimes, hotperiod, offset, depth, duration, gress)
    return np.mean(bigfracs, axis=1)

def observe_star(times, exptime, sigma, hotperiod, offset, depth, duration, gress, coldperiod, Aamp, Bamp, K=21): # MAGIC
    fluxes = np.ones_like(times)
    fluxes *= (1. - integrate_fractions(times, exptime, hotperiod, offset, depth, duration, gress, coldperiod, Aamp, Bamp, K))
    fluxes += sigma * np.random.normal(size=fluxes.shape)
    return fluxes

def ln_like(data, pars):
    times, fluxes, ivars = data
    hotperiod, offset, depth, duration, gress, coldperiod, Aamp, Bamp = pars
    fracs = integrate_fractions(times, exptime, hotperiod, offset, depth, duration, gress, coldperiod, Aamp, Bamp, 5) # MAGIC
    return -0.5 * np.sum(ivars * (fluxes - (1. - fracs)) ** 2)

def ln_prior(pars):
    return 0.

def ln_posterior(pars, data):
    lp = ln_prior(pars)
    if not np.isfinite(lp):
        return -np.Inf
    return lp + ln_like(data, pars)

if __name__ == "__main__":
    np.random.seed(42)
    times = np.arange(0., 4.1 * 365, 1.0 / 48.) # 30-min cadence in d
    exptime = ((1.0 / 24.) / 60.) * 27. # 27 min in d
    sigma = 1.e-5
    hotperiod = 6.5534 # MAGIC
    coldperiod = 365.25 * 5.0 # MAGIC
    Aamp = 2.34 / 86400. # MAGIC
    Bamp = 0.
    truepars = np.array([hotperiod, 731.55, 0.005235, 0.32322, 0.05232, coldperiod, Aamp, Bamp]) # MAGIC
    true_time_delays = times - distort_times(times, *(truepars[5:]))
    fluxes = observe_star(times, exptime, sigma, *truepars)
    plt.plot(times, fluxes, ".")
    plt.xlabel("time (d)")
    plt.ylabel("flux")
    plt.savefig("hotcold_data.png")
    ivars = np.zeros_like(fluxes) + 1. / (sigma ** 2)
    data = np.array([times, fluxes, ivars])
    initpars = truepars
    initpars[5:] = [365.25 * 12, 0., 0.] # MAGIC
    ndim, nwalkers = len(initpars), 16
    pos = [initpars + 1e-5*np.random.randn(ndim) for i in range(nwalkers)]
    nburn = 10
    for burn in range(nburn):
        nlinks = 64
        print "burning %d, ndim %d, nwalkers %d, nlinks %d" % (burn, ndim, nwalkers, nlinks)
        sampler = emcee.EnsembleSampler(nwalkers, ndim, ln_posterior, args=(data,))
        sampler.run_mcmc(pos, nlinks)
        chain = sampler.flatchain
        low = 3 * len(chain) / 4
        if nwalkers < 512:
            nwalkers *= 2
        pos = chain[np.random.randint(low, high=len(chain), size=nwalkers)]

        # plot samples
        plt.clf()
        plt.plot(times, 86400. * true_time_delays, "b-")
        for ii in np.random.randint(len(sampler.flatchain), size=16):
            time_delays = times - distort_times(times, *(sampler.flatchain[ii, 5:]))
            plt.plot(times, 86400. * time_delays, "k-", alpha=0.25)
        plt.xlabel("time (d)")
        plt.ylabel("time delay (s)")
        plt.savefig("hotcold_time_delays.png")

        # triangle-plot samples
        plt.clf()
        resids = (sampler.flatchain - truepars[None, :])
        resids[:, [0, 1, 3, 4, 6, 7]] *= 86400.
        resids[:, 2] *= 1.e6
        fig = triangle.corner(resids,
                              labels=["hot period resid (s)", "offset resid (s)", 
                                      "depth resid (ppm)", "duration resid (s)", 
                                      "gress resid (s)", "cold period resid (d)",
                                      "A amplitude resid (s)", "B amplitude resid (s)"],
                              truths=(truepars - truepars))
        fig.savefig("hotcold_triangle.png")
