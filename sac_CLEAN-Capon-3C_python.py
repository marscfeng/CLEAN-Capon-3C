# Control script for CLEAN-Capon-3c
#    by Martin Gal
#    2016 - May - 16
#
#
# For more info on the algorithm, see (doi: 10.1093/gji/ggw150)
# 'Deconvolution enhanced direction of arrival estimation using 
#  1- and 3-component seismic arrays applied to ocean induced microseisms'
#
#
#
# Python modules needed:
# Obspy, numpy,scipy, matplotlib
#
#
#
# functions used:
# ---------------
# read                   ... obspy read function
# equalize               ... checks if there are equal amout of traces and if all stations are in the correct order
# get_rxy_sac            ... extracts station locations from the SAC header (st[x].stats.sac.stla/stlo)
# remove_gain            ... removes gain, i.e. conversion to m/s
# make_subwindows        ... makes subwindows with data, mean removed and Hann taper applied
# make_csdm              ... generates the cross spectral density matrix
# CLEAN_3C_Capon         ... CLEAN procedure
# np.linalg.inv          ... numpy routine to get inverse matrix
# make_P_Capon           ... 3 component beamformer
# get_max                ... extracts maxima of strongest source on each component
# make_plot              ... Plots the beamforming results
# refine_max             ... Runs a nested grid to find a more accurate slowness vector which is used for clean iterations
#
#
#
# variables used:
# ---------------
# nsamp          ... amount of data points in a temporal subwindow
# smin           ... minimum slowness that is used to perform the slowness search [s/deg]
# smax           ... max slowness. values -50 and 50 are standard for these smin and smax
# sinc           ... the increment of the slowness. the lower the more accurate the finer the grid-search is. default value should be 0.5
# find           ... frequency at which the DOA is performed. warning: it is not [Hz]. It connected to the frequency by the equation freq = find/(nsamp*dt)
#                    where freq is in [Hz]. 
# fave           ... frequency to average over. Do not use more than 5% of find, otherwise your results can be biased in the velocity estimation.
# control        ... control parameter that extracts power (between 0-1). 0.1 is default 
# cln_iter       ... number of iterations for the CLEAN algo, set at 0, you get the normal 3C beamforming result. Set a higher value to clean spectrum.
#                    for CLEAN, try 30 and go from there depending on what you would like to achieve.
# show_peak_info ... information about peaks from which energy is removed, works for cln_iter > 0, 
#                    energy is removed from 3 components, hence there will be 3 peaks removed per iteration.
# st             ... matrix of Z data. first element is sensor station and second element is time series. dimensions are st[nr][nsamp]
# st0            ... North-South component, can also be BH1
# st1            ... East-West component or BH2
# folder         ... path to metadata directory
# meta_f         ... full path to metadata file
# dic_meta       ... dictionary with station name/location information
# nr             ... amount of array stations/sensors
# rx             ... vector of r_x component for all stations. rx is in [deg]. reference station of the array is always first sensor in the sequence.
# ry             ... vector of r_y component ..
# nwin           ... amount of time windows that need to be extracted from the time series
# dt             ... time steps. dependent on array.
# freq           ... frequency at which the DOA is performed in [Hz]
# df             ... averaging frequency
# kmin           ... minimum wavenumber. it is used later for the calculation as all angles need to be considered of the arriving signal.
#                    the steering vector is basically exp(ikr) where r is the interstation distance in [deg].
# kmax           ... max wavenumber
# kinc           ... wavenumber increment
# nk             ... amount of slowness steps/ respectively wavenumber steps from min to ma
# pdic           ... dictionary with BH1 azimuth directions. (this is made specifically for the philbara array /PSAR)
# xt             ... data split into temporal subwindows, mean removed and Hann taper applied.
# csdm           ... cross spectral density matrix
# icsdm          ... inverse csdm
# fk_cln         ... clean power spectrum 
# polariz        ... power output for Z,R,T component
# max_c          ... xy-slowness of stronges source in polariz [s/deg,s/deg]x3
# max_o          ... power of strongest source in polariz 
# Z,R,T          ... normalized power components [dB]
# src_grd_ref    ... source grid refinement, how often to refine grid in the search of a maximum.
#                    refinment ends up at: sinc/float((src_grd_ref)**2)
# min_relative_pow ... minimum in relative power [dB], for plotting
# enhance_vis      ... if true, CLEAN spectrum is convolved with a Gauss kernel for for better looks
# add_bg           ... adds background to the cleaned spectrum, can be useful if the spectrum is only parially cleaned. 
#                      Power measurements have to be taken with care though. Summation over (clean+bg spectrum) is not a viable option anymore to calculate the total power oa a component.
# inter_mode       ... Want interpolation of your plot? 'nearest' = none, or any other from here:
#                      http://matplotlib.org/examples/images_contours_and_fields/interpolation_methods.html
# area             ... size of gauss kernel to be convelved with CLEAN-spectrum (size as in pixel, area x area)
# std_g            ... standard deviation of guassian kernel, controls the extent of the kernel
# show_clean_hist  ... switch to show slowness vector removal per iteration per component. 
#                  ... useful to check if your results are stabil.
# pwrZ             ... power on the Z component from autocorrelations


import numpy as np
from obspy import read
from subroutine_CLEAN_3c import *



print '********************************************************************************************************************'
print 
print 'Capon-3C beamformer may underestimate the power of sources, but gives a more accurate source distribution with CLEAN'
print 'If you need accurate power estimates use with care, or switch to the Bartlett (fk) beamformer.'
print 
print '********************************************************************************************************************'

nsamp          = 8000 
smin           = -40.0
smax           = 40.0
sinc           = 1
find           = 80
fave           = 4
control        = 0.1
cln_iter       = 1



src_grd_ref      = 5
show_peak_info   = False
show_clean_hist  = False # this option is best used with a small control parameter and a high cln_iter value
min_relative_pow = -12         
enhance_vis      = True        
add_bg           = False                                                           
inter_mode       = 'bilinear'      
area             = 7           
std_g            = 1           






st  = read('/Users/mgal/temp_SETA/3comp/2006.315*BHZ.SAC')
st0 = read('/Users/mgal/temp_SETA/3comp/2006.315*BHN.SAC')
st1 = read('/Users/mgal/temp_SETA/3comp/2006.315*BHE.SAC') 


st,st0,st1 = equalize(st,st0,st1)
nr = st0.count()
rx,ry = get_rxy_sac(nr,st0)   

# remove gain if known and response is flat in the frequency range of interest
st, st0, st1 = remove_gain(st,st0,st1,nr,gain=1)




nwin = int(st0[0].count()/nsamp)*2-1
dt = st0[0].stats.delta
freq = find/(nsamp*dt)
kmin = smin*freq
kmax = smax*freq
kinc = sinc*freq
nk = int(((kmax-kmin)/kinc+0.5)+1) 

print 'number of nwin:',nwin
print 'npts:',st0[0].count()
print 'Amount of stations:', nr
print 'CLEAN-Capon-3C DOA estimation is performed at:','freq',freq,'+-',fave/float(nsamp*dt)


xt = make_subwindows(nr,nwin,st,st0,st1,nsamp)
csdm = make_csdm(nwin,nr,xt,nsamp,find,fave)
icsdm = np.zeros((3,3*nr,3*nr),dtype=complex)
fk_cln = np.zeros((3,nk,nk))
print
pwrZ = 10*np.log10(np.trace(csdm[0,:nr,:nr]).real) 

cln_hist = []
for cln in range(cln_iter+1):
    if cln != 0:
        csdm,fk_cln = CLEAN_3C_Capon(nr,max_c,smin,sinc,freq,rx,ry,csdm,control,fk_cln,cln,nk,show_peak_info)   
    for k in range(3):
        icsdm[k] = np.linalg.inv(csdm[k]) 
    polariz = make_P_Capon(nk,nr,kinc,kmin,rx,ry,icsdm)
    max_c, max_o = get_max(polariz,smin,sinc,cln)
    if src_grd_ref > 0:
    	max_c = refine_max_Capon(src_grd_ref,polariz,nk,nr,rx,ry,icsdm,max_c,smin,sinc,freq)
    if show_clean_hist == True:
       	cln_hist.append(max_c)


Z = (fk_cln[0])
R = (fk_cln[1])
T = (fk_cln[2])


print 'Power estimation form Z component autocorrelations: %.02f [dB]'%(pwrZ)
print 'This value includes every signal on the component, i.e. also signals'
print 'that do not pass as plain wave over the array, or noise, glitches and local stuff. '
print 'Hence this value will always be higher than the extracted CLEAN signal.'
if cln_iter > 0 :
	print '-------------------------'
	print 'Power info for strongest cleaned-source (grid size dependent):'
	print 'Total   %.02f dB'%(10*np.log10((Z+R+T).max()))
	print 'Z-comp  %.02f dB'%(10*np.log10(Z.max()))
	print 'R-comp  %.02f dB'%(10*np.log10(R.max()))
	print 'T-comp  %.02f dB'%(10*np.log10(T.max()))
	print '-------------------------'
	print
	print '-------------------------'
	print 'Power info for total cleaned power on each component:'
	print '(If power of Z from autocorrelations is smaller than' 
	print 'CLEAN power, either your step or iteration parameter'
	print 'is to large check with show_clean_hist=True)'
	print 'Total   %.02f dB'%(10*np.log10((Z+R+T).sum()))
	print 'Z-comp  %.02f dB'%(10*np.log10(Z.sum()))
	print 'R-comp  %.02f dB'%(10*np.log10(R.sum()))
	print 'T-comp  %.02f dB'%(10*np.log10(T.sum()))
	print '-------------------------'

if add_bg==True or cln_iter==0:
    Z = (fk_cln[0] + polariz[:,:,0])
    R = (fk_cln[1] + polariz[:,:,1])
    T = (fk_cln[2] + polariz[:,:,2])
if show_clean_hist == True:
	plt_hist(cln_hist,cln_iter)
make_plot(Z,R,T,smin,smax,min_relative_pow,enhance_vis,inter_mode,area,std_g)








