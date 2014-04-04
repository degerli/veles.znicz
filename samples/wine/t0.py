t0 = {"S0": 0,
      'count_model': 1,
      'count_model_example': 1,
      'models_train': {'model0': {'number': 1,
                                  'type_model': 'NS',
                                  'data_model': 'wine/model_WF_wine.py'}},
      'use_random': 1,
      'random': {'type_seed': 0,
                 'seed': 'scripts/seed',
                 'type': 1},
      'data_set': {'data': 'wine/config_data2.py',
                   'merge_dataset': 1,
                   'type1': 1,
                   'var1': {'use_rand_for_train_data': 1,
                            'use_rand_for_valid_data': 1,
                            'use_rand_for_test_data': 0,
                            'divideblock': 1,
                            'size_fix_div': {'sizeTR ': range(1, 5),
                                             'sizeV': range(5, 9),
                                             'sizeTE': range(9, 13)},
                            'size_proc_div': {'sizeTR%': 0.7,
                                              'sizeV%': 0.3}  # 'sizeTE%':0.15}
                            },
                   'not_merge_type': 0,
                   'index_file': {'ind_fileTR': [1],
                                  'ind_fileTV': [0],
                                  'ind_fileTE': [0]},
                   'f_index_file': {'file_ind_fileTR': 'xor/indTR.cfg',
                                    'file_ind_fileTV': 'xor/indTV.cfg',
                                    'file_ind_fileTE': 'xor/indTE.cfg'},
                   'use_norm': 5,
                   'norm': {'d_1': 1,
                            'min': (-1),
                            'max': 1,
                            'minmax': 1,
                            'meanstd': 1,
                            'removeconstantrows': 0}},
      'train_param': {'type': 'BP1',
                      'global_alpha': 0.9,
                      'global_lambda': 0.0,
                      'threshold': 1.0,
                      'threshold_low': 1.0}}