import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, ConcatDataset
from transformers import *
import torch.utils.data as Data
import pickle


class Translator:
    """Backtranslation. Here to save time, we pre-processing and save all the translated data into pickle files.
    """

    def __init__(self, path, data_set, transform_type='BackTranslation'):
        if data_set == 'Yahoo':    
            # Pre-processed German data
            with open(path + 'yahoo_train_german.pkl', 'rb') as f:
                self.de = pickle.load(f)
            # Pre-processed Russian data
            with open(path + 'yahoo_train_russian.pkl', 'rb') as f:
                self.ru = pickle.load(f)
        
        elif data_set == 'OOD':
            # Pre-processed German data
            with open(path + 'OOD_concatenated_german.pkl', 'rb') as f:
                self.de = pickle.load(f)
            # Pre-processed Russian data
            with open(path + 'OOD_concatenated_russian.pkl', 'rb') as f:
                self.ru = pickle.load(f)
        else:
            pass


    def __call__(self, ori, idx):
        out1 = self.de[idx]
        out2 = self.ru[idx]
        return out1, out2, ori
    
# class Translator_ood:
#     """Backtranslation. Here to save time, we pre-processing and save all the translated data into pickle files.
#     """

#     def __init__(self, path, transform_type='BackTranslation'):
#         # Pre-processed German data
#         with open(path + 'OOD_concatenated_german.pkl', 'rb') as f:
#             self.de = pickle.load(f)
#         # Pre-processed Russian data
#         with open(path + 'OOD_concatenated_russian.pkl', 'rb') as f:
#             self.ru = pickle.load(f)

#     def __call__(self, ori, idx):
#         out1 = self.de[idx]
#         out2 = self.ru[idx]
#         return out1, out2, ori

def get_data(data_path, n_labeled_per_class, unlabeled_per_class=5000, max_seq_len=256, model='bert-base-uncased', train_aug=False):
    """Read data, split the dataset, and build dataset for dataloaders.

    Arguments:
        data_path {str} -- Path to your dataset folder: contain a train.csv and test.csv
        n_labeled_per_class {int} -- Number of labeled data per class

    Keyword Arguments:
        unlabeled_per_class {int} -- Number of unlabeled data per class (default: {5000})
        max_seq_len {int} -- Maximum sequence length (default: {256})
        model {str} -- Model name (default: {'bert-base-uncased'})
        train_aug {bool} -- Whether performing augmentation on labeled training set (default: {False})

    """
    # Load the tokenizer for bert
    tokenizer = BertTokenizer.from_pretrained(model)

    train_df = pd.read_csv(data_path+'reduced_data/yahoo_train.csv', index_col = 0)
    ood_df = pd.read_csv(data_path+'reduced_data/OOD_concatenated.csv', index_col = 0)
    test_df = pd.read_csv(data_path+'reduced_data/yahoo_test.csv', index_col = 0)

    # Here we only use the bodies and removed titles to do the classifications
#     train_labels = np.array([v-1 for v in train_df['labels']])
#     train_text = np.array([v for v in train_df['content']])

#     ood_text = np.array([v for v in ood_df['content']])

#     test_labels = np.array([u-1 for u in test_df['labels']])
#     test_text = np.array([v for v in test_df['content']])
    
    train_labels = train_df['labels']
    train_text = train_df['content']

    ood_text = ood_df['content']

    test_labels = test_df['labels']
    test_text = test_df['content']

    n_labels = max(test_labels) + 1

    # Split the labeled training set, unlabeled training set, development set
    # train_labeled_idxs, train_unlabeled_idxs, val_idxs = train_val_split(
    #     train_labels, n_labeled_per_class, unlabeled_per_class, n_labels)

    train_labeled_idxs = torch.load(data_path+"/indices/msr_30_equal_100_labeled_indices.pt")
    train_unlabeled_idxs_yahoo = torch.load(data_path+"/indices/msr_30_idr_5_50000_unlabeled_indices.pt")['in_domain_idx']
    train_unlabeled_idxs_ood = torch.load(data_path+"/indices/msr_30_idr_5_50000_unlabeled_indices.pt")['out_of_domain_idx']
    val_idxs = torch.load(data_path+"/indices/eval_indices.pt")


    # Build the dataset class for each set
    train_labeled_dataset = loader_labeled(
        train_text.loc[train_labeled_idxs], train_labels.loc[train_labeled_idxs], tokenizer, max_seq_len, train_aug)
    
    yahoo_unlabeled_dataset = loader_unlabeled(
        train_text.loc[train_unlabeled_idxs_yahoo], train_unlabeled_idxs_yahoo, 
        tokenizer, max_seq_len, Translator(data_path+'all_backtranslations/', 'Yahoo'))
    
    ood_unlabeled_dataset = loader_OOD(
        ood_text.loc[train_unlabeled_idxs_ood], train_unlabeled_idxs_ood, 
        tokenizer, max_seq_len, Translator(data_path+'all_backtranslations/', 'OOD')
    )

    train_unlabeled_dataset = ConcatDataset([yahoo_unlabeled_dataset, ood_unlabeled_dataset])
    
    
    val_dataset = loader_labeled(
        train_text[val_idxs], train_labels[val_idxs], tokenizer, max_seq_len)
    test_dataset = loader_labeled(
        test_text, test_labels, tokenizer, max_seq_len)

    print("#Labeled: {}, Unlabeled_yahoo {}, Unlabeled_ood {}, Val {}, Test {}".format(len(
        train_labeled_idxs), len(train_unlabeled_idxs_yahoo), len(train_unlabeled_idxs_ood), len(val_idxs), len(test_labels)))

    return train_labeled_dataset, train_unlabeled_dataset, val_dataset, test_dataset, n_labels


def train_val_split(labels, n_labeled_per_class, unlabeled_per_class, n_labels, seed=0):
    """Split the original training set into labeled training set, unlabeled training set, development set

    Arguments:
        labels {list} -- List of labeles for original training set
        n_labeled_per_class {int} -- Number of labeled data per class
        unlabeled_per_class {int} -- Number of unlabeled data per class
        n_labels {int} -- The number of classes

    Keyword Arguments:
        seed {int} -- [random seed of np.shuffle] (default: {0})

    Returns:
        [list] -- idx for labeled training set, unlabeled training set, development set
    """
    np.random.seed(seed)
    labels = np.array(labels)
    train_labeled_idxs = []
    train_unlabeled_idxs = []
    val_idxs = []

    for i in range(n_labels):
        idxs = np.where(labels == i)[0]
        np.random.shuffle(idxs)
        if n_labels == 2:
            # IMDB
            train_pool = np.concatenate((idxs[:500], idxs[5500:-2000]))
            train_labeled_idxs.extend(train_pool[:n_labeled_per_class])
            train_unlabeled_idxs.extend(
                idxs[500: 500 + 5000])
            val_idxs.extend(idxs[-2000:])
        elif n_labels == 10:
            # DBPedia
            train_pool = np.concatenate((idxs[:500], idxs[10500:-2000]))
            train_labeled_idxs.extend(train_pool[:n_labeled_per_class])
            train_unlabeled_idxs.extend(
                idxs[500: 500 + unlabeled_per_class])
            val_idxs.extend(idxs[-2000:])
        else:
            # Yahoo/AG News
            train_pool = np.concatenate((idxs[:500], idxs[5500:-2000]))
            train_labeled_idxs.extend(train_pool[:n_labeled_per_class])
            train_unlabeled_idxs.extend(
                idxs[500: 500 + 5000])
            val_idxs.extend(idxs[-2000:])
    np.random.shuffle(train_labeled_idxs)
    np.random.shuffle(train_unlabeled_idxs)
    np.random.shuffle(val_idxs)

    return train_labeled_idxs, train_unlabeled_idxs, val_idxs
    

class loader_labeled(Dataset):
    # Data loader for labeled data
    def __init__(self, dataset_text, dataset_label, tokenizer, max_seq_len, aug=False):
        self.tokenizer = tokenizer
        self.text = dataset_text
        self.labels = dataset_label
        self.max_seq_len = max_seq_len

        self.aug = aug
        self.trans_dist = {}

        if aug:
            print('Aug train data by back translation of German')
            self.en2de = torch.hub.load(
                'pytorch/fairseq', 'transformer.wmt19.en-de.single_model', tokenizer='moses', bpe='fastbpe')
            self.de2en = torch.hub.load(
                'pytorch/fairseq', 'transformer.wmt19.de-en.single_model', tokenizer='moses', bpe='fastbpe')

    def __len__(self):
        return len(self.labels)

    def augment(self, text):
        if text not in self.trans_dist:
            self.trans_dist[text] = self.de2en.translate(self.en2de.translate(
                text,  sampling=True, temperature=0.9),  sampling=True, temperature=0.9)
        return self.trans_dist[text]

    def get_tokenized(self, text):
        tokens = self.tokenizer.tokenize(text)
        if len(tokens) > self.max_seq_len:
            tokens = tokens[:self.max_seq_len]
        length = len(tokens)

        encode_result = self.tokenizer.convert_tokens_to_ids(tokens)
        padding = [0] * (self.max_seq_len - len(encode_result))
        encode_result += padding

        return encode_result, length

    def __getitem__(self, idx):
        if self.aug:
            text = self.text[idx]
            text_aug = self.augment(text)
            text_result, text_length = self.get_tokenized(text)
            text_result2, text_length2 = self.get_tokenized(text_aug)
            return ((torch.tensor(text_result), torch.tensor(text_result2)), (self.labels[idx], self.labels[idx]), (text_length, text_length2))
        else:
            text = self.text[idx]
            tokens = self.tokenizer.tokenize(text)
            if len(tokens) > self.max_seq_len:
                tokens = tokens[:self.max_seq_len]
            length = len(tokens)
            encode_result = self.tokenizer.convert_tokens_to_ids(tokens)
            padding = [0] * (self.max_seq_len - len(encode_result))
            encode_result += padding
            return (torch.tensor(encode_result), self.labels[idx], length)


class loader_unlabeled(Dataset):
    # Data loader for unlabeled data (Yahoo)
    def __init__(self, dataset_text, unlabeled_idxs, tokenizer, max_seq_len, aug=None):
        self.tokenizer = tokenizer

        self.text = dataset_text
        self.ids = unlabeled_idxs

        # self.ood_text = ood_text
        # self.ood_idxs = ood_idxs

        # self.text = self.text.extend(self.ood_text)

        self.aug = aug
        self.max_seq_len = max_seq_len

    def __len__(self):
        return len(self.text)

    def get_tokenized(self, text):
        tokens = self.tokenizer.tokenize(text)
        if len(tokens) > self.max_seq_len:
            tokens = tokens[:self.max_seq_len]
        length = len(tokens)
        encode_result = self.tokenizer.convert_tokens_to_ids(tokens)
        padding = [0] * (self.max_seq_len - len(encode_result))
        encode_result += padding
        return encode_result, length

    def __getitem__(self, idx):
        if self.aug is not None:
            u, v, ori = self.aug(self.text[idx], self.ids[idx])
            encode_result_u, length_u = self.get_tokenized(u)
            encode_result_v, length_v = self.get_tokenized(v)
            encode_result_ori, length_ori = self.get_tokenized(ori)
            return ((torch.tensor(encode_result_u), torch.tensor(encode_result_v), torch.tensor(encode_result_ori)), (length_u, length_v, length_ori))
        else:
            text = self.text[idx]
            encode_result, length = self.get_tokenized(text)
            return (torch.tensor(encode_result), length)
        
class loader_OOD(Dataset):
    # Data loader for unlabeled data OOD
    def __init__(self, ood_text, ood_idxs, tokenizer, max_seq_len, aug=None):
        self.tokenizer = tokenizer

        # self.text = dataset_text
        # self.ids = unlabeled_idxs

        self.ood_text = ood_text
        self.ood_idxs = ood_idxs

        self.text = self.ood_text

        self.aug = aug
        self.max_seq_len = max_seq_len

    def __len__(self):
        return len(self.ood_text)

    def get_tokenized(self, text):
        tokens = self.tokenizer.tokenize(text)
        if len(tokens) > self.max_seq_len:
            tokens = tokens[:self.max_seq_len]
        length = len(tokens)
        encode_result = self.tokenizer.convert_tokens_to_ids(tokens)
        padding = [0] * (self.max_seq_len - len(encode_result))
        encode_result += padding
        return encode_result, length

    def __getitem__(self, idx):
        if self.aug is not None:
            u, v, ori = self.aug(self.text[idx], self.ids[idx])
            encode_result_u, length_u = self.get_tokenized(u)
            encode_result_v, length_v = self.get_tokenized(v)
            encode_result_ori, length_ori = self.get_tokenized(ori)
            return ((torch.tensor(encode_result_u), torch.tensor(encode_result_v), torch.tensor(encode_result_ori)), (length_u, length_v, length_ori))
        else:
            text = self.text[idx]
            encode_result, length = self.get_tokenized(text)
            return (torch.tensor(encode_result), length)