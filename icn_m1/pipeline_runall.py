import sys
# insert at 1, 0 is the script path (or '' in REPL)
sys.path.insert(1, 'C:/Users/Pilin/Documents/GitHub/icn/icn_m1')
import filter
import IO
import projection
import online_analysis
import offline_analysis
import rereference
import numpy as np
import json
import os
import pickle 
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import Axes3D #for 3D plotting
import scipy
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, roc_auc_score
from sklearn.model_selection import train_test_split
import itertools
import mne
mne.set_log_level(verbose='warning') #to avoid info at terminal
from collections import Counter


#%%
settings = {}
settings['BIDS_path'] = "C:\\Users\Pilin\Dropbox (Partners HealthCare)\Timon_raw_data\\"
settings['out_path'] = "C:\\Users\Pilin\Dropbox (Partners HealthCare)\Experiments\ProcessedTimonData\Data_processed\\"
settings['resamplingrate']=10
settings['max_dist_cortex']=20
settings['max_dist_subcortex']=5
settings['normalization_time']=10
settings['frequencyranges']=[[4, 8], [8, 12], [13, 20], [20, 35], [13, 35], [60, 80], [90, 200], [60, 200]]
settings['seglengths']=[1, 2, 2, 3, 3, 3, 10, 10, 10]


settings['BIDS_path']=settings['BIDS_path'].replace("\\", "/")
settings['out_path']=settings['out_path'].replace("\\", "/")

with open('settings/mysettings.json', 'w') as fp:
    json.dump(settings, fp)
    
settings = IO.read_settings('mysettings')
#2. write _channels_MI file
IO.write_all_M1_channel_files()
#3. get all vhdr files (from a subject or from all BIDS_path)
vhdr_files=IO.get_all_vhdr_files(settings['BIDS_path'])

#4. read grid
#%% grid projection
#read grid from session
cortex_left, cortex_right, subcortex_left, subcortex_right = IO.read_grid()
grid_ = [cortex_left, subcortex_left, cortex_right, subcortex_right]
#%% plotting
ecog_grid_left = grid_[0]
ecog_grid_right = grid_[2]

# fig = plt.figure(dpi=100)
# ax = fig.add_subplot(111, projection='3d')
# ax.scatter(ecog_grid_left[0,:], ecog_grid_left[1,:],ecog_grid_left[2,:], zdir='z', s=20, c=None, depthshade=True, label='contralateral')
# ax.scatter(ecog_grid_right[0,:], ecog_grid_right[1,:],ecog_grid_right[2,:], zdir='z', s=20, c=None, depthshade=True, label='ipsilateral')

# ax.view_init(azim=0, elev=90)
# plt.legend()
# plt.title('grid matrix')


# stn_grid_left = grid_[1]
# stn_grid_right = grid_[3]

# fig = plt.figure(dpi=100)
# ax = fig.add_subplot(111, projection='3d')
# ax.scatter(stn_grid_left[0,:], stn_grid_left[1,:],stn_grid_left[2,:], zdir='z', s=20, c=None, depthshade=True, label='contralateral')
# ax.scatter(stn_grid_right[0,:], stn_grid_right[1,:],stn_grid_right[2,:], zdir='z', s=20, c=None, depthshade=True, label='ipsilateral')
# ax.view_init(azim=0, elev=90)
# plt.legend()
# plt.title('STN grid')

#%%
for s in range(0, 17):
   
    if s<10:
        subject_path=settings['BIDS_path'] + 'sub-00' + str(s)
    else:
        subject_path=settings['BIDS_path'] + 'sub-0' + str(s)
    
        
    subfolder=IO.get_subfolders(subject_path)
           
    vhdr_files=IO.get_files(subject_path, subfolder)
    
    len(vhdr_files)
    for f in range(len(vhdr_files)):
        #%% 5. get info and files for the specific subject/session/run

        vhdr_file=vhdr_files[f]
        
        
        #get info from vhdr_file
        subject, run, sess = IO.get_sess_run_subject(vhdr_file)
        
        print('RUNNIN SUBJECT_'+ subject+ '_SESS_'+ sess + '_RUN_' + run)

        
        #read sf
        sf=IO.read_run_sampling_frequency(vhdr_file)
        if len(sf.unique())==1: #all sf are equal
            sf=int(sf[0])
        else: 
            Warning('Different sampling freq.')      
        #read data
        bv_raw, ch_names = IO.read_BIDS_file(vhdr_file)
        
        #check session
        sess_right = IO.sess_right(sess)
        print(sess_right)
        
        # read channels info
        used_channels = IO.read_M1_channel_specs(vhdr_file[:-10])

        #used_channels = IO.read_used_channels() #old
        print(used_channels)
        
        # extract used channels/labels from brainvision file, split up in cortex/subcortex/labels
        #dat_ is a dict
        dat_ = IO.get_dat_cortex_subcortex(bv_raw, ch_names, used_channels)
        ind_cortex=dat_['ind_cortex']
        ind_subcortex=dat_['ind_subcortex']
        dat_ECOG=dat_['dat_cortex']
        dat_MOV=dat_['dat_label']
        dat_STN=dat_['dat_subcortex']
        
               
        
        #%% 6. rereference
        dat_ECOG_r, dat_STN_r =rereference.rereference(run_string=vhdr_file[:-10], data_cortex=dat_ECOG, data_subcortex=dat_STN)
        #%% 7. detet bad-channels.      
                
        #%% 8. project data to grid points
        #read all used coordinates from session coordinates.tsv BIDS file
        coord_patient = IO.get_patient_coordinates(ch_names, ind_cortex, ind_subcortex, vhdr_file, settings['BIDS_path'])
        # # # given those coordinates and the provided grid, estimate the projection matrix
        proj_matrix_run = projection.calc_projection_matrix(coord_patient, grid_, sess_right, settings['max_dist_cortex'], settings['max_dist_subcortex'])
        # #They show the relative weights of every channel for every gridpoint
        # #if Empty, then that grid is not used
        # plt.subplot(); plt.imshow(proj_matrix_run[0], aspect='auto'); cbar = plt.colorbar(); cbar.set_label('projection weight')
        # plt.xlabel('channels'); plt.ylabel('grid points'); plt.title('ECOG projection matrix')
                          
        # #%% this function tells you which points are actually active after the projection
        arr_act_grid_points = IO.get_active_grid_points(sess_right, used_channels['labels'], ch_names, proj_matrix_run, grid_)

        #%%
        seglengths = settings['seglengths']
        
        # read line noise from participants.tsv
        line_noise = IO.read_line_noise(settings['BIDS_path'],subject)
        if s==16:
            filter_len=sf
        else:
            filter_len=1001
        # get the lenght of the recording signals
        recording_time = bv_raw.shape[1] 
        
        #resample
        normalization_samples = settings['normalization_time']*settings['resamplingrate']
        new_num_data_points = int((bv_raw.shape[1]/sf)*settings['resamplingrate'])
    
        # downsample_idx states the original brainvision sample indexes are used
        downsample_idx = (np.arange(0,new_num_data_points,1)*sf/settings['resamplingrate']).astype(int)
        
        # get filter coef?
        
        filter_fun = filter.calc_band_filters(settings['frequencyranges'], sample_rate=sf, filter_len=filter_len)
    
        offset_start = int((sf/seglengths[0]) / (sf/settings['resamplingrate']))
        
        rf_data_median, pf_data_median = offline_analysis.run(sf, settings['resamplingrate'], np.asarray(seglengths), settings['frequencyranges'], grid_, downsample_idx, bv_raw, line_noise, \
                      sess_right, dat_, filter_fun, proj_matrix_run, arr_act_grid_points, new_num_data_points, ch_names, normalization_samples)
        
        #%%ipsi o contralateral mov
    
        label_channels = np.array(ch_names)[used_channels['labels']]
        con_true = np.empty(len(label_channels), dtype=object)
        y=np.empty((len(dat_MOV),new_num_data_points-offset_start), dtype=object)
        label_baseline_corrected=[]
        label_baseline_corrected_onoff=[]
        raw_label_baseline=[]

        #only contralateral mov
        for m in range(len(label_channels)):
            #right session
            if sess_right is True:
                if 'RIGHT' in label_channels[m]:
                    con_true[m]=False
                else:
                    con_true[m]=True

            #left session        
            else:
                if 'RIGHT' in label_channels[m]:
                    con_true[m]=True

                else:
                    con_true[m]=False
                    
            if subject == '016':
                Df=55
                target_channel_corrected, onoff, raw_target_channel=offline_analysis.baseline_correction(y=-dat_MOV[m], Decimate=Df,method='baseline_rope', param=1e-1, thr=2e-1, normalize=True)
            else:
                Df=40
                target_channel_corrected, onoff, raw_target_channel=offline_analysis.baseline_correction(y=dat_MOV[m], Decimate=Df,method='baseline_rope', param=1e5, thr=2e-1, normalize=True)

            events=offline_analysis.create_events_array(onoff=onoff, raw_target_channel=dat_MOV[m], sf=sf)
    
            label=offline_analysis.generate_continous_label_array(L=new_num_data_points, sf=settings['resamplingrate'], events=events) 
            y[m]=label[offset_start:]        

           
            if m==0:
                label_baseline_corrected=target_channel_corrected
                label_baseline_corrected_onoff=onoff
                raw_label_baseline=raw_target_channel
            else:
                label_baseline_corrected=np.vstack((label_baseline_corrected,target_channel_corrected))
                label_baseline_corrected_onoff=np.vstack((label_baseline_corrected_onoff,onoff))
                raw_label_baseline=np.vstack((raw_label_baseline, raw_target_channel))
                
            
            # label=offline_analysis.generate_continous_label_array(L=len(dat_MOV[m]), sf=sf, events=events) 
            # y[m]=label[1000:-1:100] 
            
        #%%save data
        run_ = {
            "vhdr_file" : vhdr_file,
            "resamplingrate" : settings['resamplingrate'],
            "BIDS_path" : settings['BIDS_path'], 
            "projection_grid" : grid_, 
            "bv_raw" : bv_raw, 
            "ch_names" : ch_names, 
            "data_" : dat_,
            "subject" : subject, 
            "run" : run, 
            "sess" : sess, 
            "sess_right" :  sess_right, 
            "used_channels" : used_channels, 
            "coord_patient" : coord_patient, 
            "proj_matrix_run" : proj_matrix_run, 
            "fs" : sf, 
            "line_noise" : line_noise, 
            "seglengths" : seglengths, 
            "normalization_samples" : normalization_samples, 
            "new_num_data_points" : new_num_data_points, 
            "downsample_idx" : downsample_idx, 
            "filter_fun" : filter_fun, 
            "offset_start" : offset_start, 
            "arr_act_grid_points" : arr_act_grid_points, 
            "rf_data_median" : rf_data_median, 
            "pf_data_median" : pf_data_median,
            "raw_label_baseline" : raw_label_baseline,
            "label_baseline_corrected" : label_baseline_corrected, 
            "label_baseline_corrected_onoff" : label_baseline_corrected_onoff,
            "label" : y, 
            "label_con_true" : con_true,        
        }

        out_path = os.path.join(settings['out_path'],'sub_' + subject + '_sess_' + sess + '_run_' + run + '.p')
    
        with open(out_path, 'wb') as handle:
            pickle.dump(run_, handle, protocol=pickle.HIGHEST_PROTOCOL)    

                                
   