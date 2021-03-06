import os
import cv2
import time
import random
import numpy as np
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
# import torchvision.transforms as T
from torchvision.utils import make_grid
from torchvision.models import resnet50
from torchsummary import summary
from sklearn.model_selection import train_test_split
from PIL import Image
import matplotlib.pyplot as plt
import transforms as T
from torch.utils.tensorboard import SummaryWriter

# %matplotlib inline
folderDir = r"./" # for local run
# folderDir = '/content/drive/MyDrive/Question5/' # for colab run with Google drive mounted.
MODEL_PATH = folderDir+ "Code/Rest50Best_RandomErase.pth"
LOG_PATH = folderDir+ "Code/TensorBoardLog.json"
DIR_TRAIN = folderDir+ "Data/train/"
DIR_TEST = folderDir+ "Data/test/"

device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')

train_logs = {"loss" : [], "accuracy" : [], "time" : []}
val_logs = {"loss" : [], "accuracy" : [], "time" : []}

imgs = os.listdir(DIR_TRAIN) 
test_imgs = os.listdir(DIR_TEST)

dogs_list = [img for img in imgs if img.split(".")[0] == "dog"]
cats_list = [img for img in imgs if img.split(".")[0] == "cat"]

class_to_int = {"dog" : 0, "cat" : 1}
int_to_class = {0 : "dog", 1 : "cat"}
objNames = ['dog','cat']

writer = SummaryWriter(folderDir + 'Code/ResNet50_RandomErase_experience')

def get_train_transform():
    return T.Compose([
        T.RandomHorizontalFlip(p=0.5),
        T.RandomRotation(15),
        T.RandomCrop(204),
        T.ToTensor(),
        T.Normalize((0, 0, 0),(1, 1, 1)),
        T.RandomErasing()
    ])
    
def get_val_transform():
    return T.Compose([
        T.ToTensor(),
        T.Normalize((0, 0, 0),(1, 1, 1))
    ])
class CatDogDataset(Dataset):
    
    def __init__(self, imgs, class_to_int, mode = "train", transforms = None):
        
        super().__init__()
        self.imgs = imgs
        self.class_to_int = class_to_int
        self.mode = mode
        self.transforms = transforms
        
    def __getitem__(self, idx):
        image_name = self.imgs[idx]
        if self.mode == "train" or self.mode == "val":
            img = Image.open(DIR_TRAIN + image_name)
            img = img.resize((224, 224))
            ### Preparing class label
            label = self.class_to_int[image_name.split(".")[0]]
            label = torch.tensor(label, dtype = torch.float32)

            ### Apply Transforms on image
            img = self.transforms(img)

            return img, label
        
        elif self.mode == "test":
            img = Image.open(DIR_TEST + image_name)
            img = img.resize((224, 224))
            ### Apply Transforms on image
            img = self.transforms(img)

            return img
            
    def __len__(self):
        return len(self.imgs)

train_imgs, val_imgs = train_test_split(imgs, test_size = 0.25)
train_dataset = CatDogDataset(train_imgs, class_to_int, mode = "train", transforms = get_train_transform())
val_dataset = CatDogDataset(val_imgs, class_to_int, mode = "val", transforms = get_val_transform())
test_dataset = CatDogDataset(test_imgs, class_to_int, mode = "test", transforms = get_val_transform())

train_data_loader = DataLoader(
    dataset = train_dataset,
    num_workers = 8,
    batch_size = 32,
    shuffle = True
)

val_data_loader = DataLoader(
    dataset = val_dataset,
    num_workers = 8,
    batch_size = 32,
    shuffle = True
)

test_data_loader = DataLoader(
    dataset = test_dataset,
    num_workers = 8,
    batch_size = 32,
    shuffle = True
)
# if __name__ == '__main__':
    # for images, labels in train_data_loader:
        # fig, ax = plt.subplots(figsize = (50, 50))
        # ax.set_xticks([])
        # ax.set_yticks([])
        # ax.imshow(make_grid(images, 4).permute(1,2,0))
        # break
    # plt.show()    

def accuracy(preds, trues):
    preds = [1 if preds[i] >= 0.5 else 0 for i in range(len(preds))]
    ### Calculating accuracy by comparing predictions with true labels
    acc = [1 if preds[i] == trues[i] else 0 for i in range(len(preds))]
    ### Summing over all correct predictions
    acc = np.sum(acc) / len(preds)
    return (acc * 100)
    
def train_one_epoch(train_data_loader):
    epoch_loss = []
    epoch_acc = []
    start_time = time.time()
    i=0
    for images, labels in train_data_loader:
        i+=1
        images = images.to(device)
        labels = labels.to(device)
        labels = labels.reshape((labels.shape[0], 1)) 
        optimizer.zero_grad()
        preds = model(images)
        _loss = criterion(preds, labels)
        loss = _loss.item()
        epoch_loss.append(loss)
        acc = accuracy(preds, labels)
        epoch_acc.append(acc)
        #Backward
        # writer.add_scalar('Loss (item)', loss, i)
        # writer.add_scalar('Accuracy (item)', acc, i)
        _loss.backward()
        optimizer.step()
    ###Overall Epoch Results
    end_time = time.time()
    total_time = end_time - start_time
    ###Acc and Loss
    epoch_loss = np.mean(epoch_loss)
    epoch_acc = np.mean(epoch_acc)
    ###Storing results to logs
    train_logs["loss"].append(epoch_loss)
    train_logs["accuracy"].append(epoch_acc)
    train_logs["time"].append(total_time)
    return epoch_loss, epoch_acc, total_time

def val_one_epoch(val_data_loader, best_val_acc):
    
    ### Local Parameters
    epoch_loss = []
    epoch_acc = []
    start_time = time.time()
    
    ###Iterating over data loader
    for images, labels in val_data_loader:
        #Loading images and labels to device
        images = images.to(device)
        labels = labels.to(device)
        labels = labels.reshape((labels.shape[0], 1)) # [N, 1] - to match with preds shape
        #Forward
        preds = model(images)
        #Calculating Loss
        _loss = criterion(preds, labels)
        loss = _loss.item()
        epoch_loss.append(loss)
        #Calculating Accuracy
        acc = accuracy(preds, labels)
        epoch_acc.append(acc)
    
    ###Overall Epoch Results
    end_time = time.time()
    total_time = end_time - start_time
    
    ###Acc and Loss
    epoch_loss = np.mean(epoch_loss)
    epoch_acc = np.mean(epoch_acc)
    
    ###Storing results to logs
    val_logs["loss"].append(epoch_loss)
    val_logs["accuracy"].append(epoch_acc)
    val_logs["time"].append(total_time)
    
    ###Saving best model
    if epoch_acc > best_val_acc:
        best_val_acc = epoch_acc
        torch.save(model.state_dict(), MODEL_PATH)
    return epoch_loss, epoch_acc, total_time, best_val_acc

model = resnet50(pretrained = True)

model.fc = nn.Sequential(
    nn.Linear(2048, 1, bias = True),
    nn.Sigmoid()
)        
# Optimizer
optimizer = torch.optim.Adam(model.parameters(), lr = 0.0001)
# Learning Rate Scheduler
lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size = 5, gamma = 0.5)
#Loss Function
criterion = nn.BCELoss()


# # Uncommend at local run
# model.to(device)
# checkpoint = torch.load(MODEL_PATH, map_location=torch.device('cpu'))
# model.load_state_dict(checkpoint)
# model.eval()

   
def plot_image(image, label):
        plt.imshow(image, interpolation='spline16')
        plt.title(label)
        plt.show()

def predict(index, show_image = True):
                
        

        input = test_dataset[index]
        loader = DataLoader(input, batch_size= 1, shuffle= False, num_workers= 1, pin_memory= False)
        with torch.no_grad():
            image = loader.dataset
            image = torch.reshape(image, [1, image.shape[0], image.shape[1], image.shape[2]])
            #device = torch.device('cuda')
            image = image.to(device)
            #device = torch.device('cuda')
            model.cuda()
            output = model(image)
            if output.data > 0.5:
                label = "Class: Cat"
            else:
                label = "Class: Dog"
            X = image.cpu().detach().numpy().transpose([0,2,3,1])[0]
            if show_image:
                plot_image(X, label)

def ShowModelStructure():
    summary(model, input_size=(3, 224, 224))
def test(index, show_image = True):
    if index < 0:
        index = 0
    if index > len(test_dataset):
        index = len(test_dataset) -1

    input = test_dataset[index]
    loader = torch.utils.data.DataLoader(input, batch_size= 1, shuffle = False, num_workers=1, pin_memory= False)
    (img, target) = loader
    if torch.cuda.is_available():
        img = img.cuda()
        target = target.cuda()
    
    checkpoint = torch.load(MODEL_PATH, map_location=torch.device('cpu'))
    model.load_state_dict(checkpoint)
    model.eval()
        
    output = model(img)
    print('Output: {}'.format(output))
    _, pred = torch.max(output.data, dim=1)
    y_pred = pred.cpu().numpy().tolist()[0]
    y_truth = target.cpu().numpy().tolist()[0]
    probability = torch.softmax(output, dim=1).cpu().tolist()[0]
    X = img.cpu().numpy().transpose([0,2,3,1])[0]
    if show_image:
        PlotImg(X, y_truth, y_pred, probability)
        
def trainModel(epochs):
    if __name__ == '__main__':
        best_val_acc = 0
        for epoch in range(epochs):
            ###Training
            print('start training epoch ', epoch)
            loss, acc, _time = train_one_epoch(train_data_loader)
            
            writer.add_scalar('Loss (epoch)', loss, epoch)
            writer.add_scalar('Accuracy (epoch)', acc, epoch)
            #Print Epoch Details
            print("\nTraining")
            print("Epoch {}".format(epoch+1))
            print("Loss : {}".format(round(loss, 4)))
            print("Acc : {}".format(round(acc, 4)))
            print("Time : {}".format(round(_time, 4)))
            
            ###Validation
            loss, acc, _time, best_val_acc = val_one_epoch(val_data_loader, best_val_acc)
            
            
            #Print Epoch Details
            print("\nValidating")
            print("Epoch {}".format(epoch+1))
            print("Loss : {}".format(round(loss, 4)))
            print("Acc : {}".format(round(acc, 4)))
            print("Time : {}".format(round(_time, 4)))
        
        writer.export_scalars_to_json(LOG_PATH)
        writer.close()
        ### Plotting Results
        with open('compare.txt', 'a') as f:
            f.write('{}\n'.format(acc))
        #Loss
        plt.title("Loss")
        plt.plot(np.arange(1, 11, 1), train_logs["loss"], color = 'blue')
        plt.plot(np.arange(1, 11, 1), val_logs["loss"], color = 'yellow')
        plt.xlabel("Epochs")
        plt.ylabel("Loss")
        plt.show()

        #Accuracy
        plt.title("Accuracy")
        plt.plot(np.arange(1, 11, 1), train_logs["accuracy"], color = 'blue')
        plt.plot(np.arange(1, 11, 1), val_logs["accuracy"], color = 'yellow')
        plt.xlabel("Epochs")
        plt.ylabel("Accuracy")
        plt.show()

def show_before_after(path_compare:str = None):
        for images, labels in train_data_loader:
            fig, ax = plt.subplots(figsize = (50, 50))
            ax.set_xticks([])
            ax.set_yticks([])
            ax.imshow(make_grid(images, 8).permute(1,2,0))
            break
        plt.show()
        if path_compare:
            acc_value = []
            with open(path_compare, 'r') as f:
                for line in f.readlines():
                    line = line.strip()
                    acc_value.append(float(line))
            def bar_plot(acc_value, label_names = ['Before Random Erasing', 'After Random Erasing']):
                fig = plt.figure()
                plt.bar(label_names, acc_value)
                plt.show()
            
            bar_plot(acc_value)


# trainModel(10)