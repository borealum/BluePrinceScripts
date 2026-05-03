import random

#0  "Aquarium",
#1  "Billiard Room", 
#2  "Boudoir", 
#3  "Bunk Room", 
#4  "Cloister", 
#5  "Closet", 
#6  "Courtyard",  
#7  "Guest Bedroom",
#8  "Hallway", 
#9  "Mail Room", 
#10 "Nook", 
#11 "Nursery", 
#12 "Parlor", 
#13 "Spare Room", 
#14 "Storeroom"

roomNames = ["Aquarium", "Billiard Room", "Boudoir", "Bunk Room", "Cloister",
 "Closet", "Courtyard", "Guest Bedroom", "Hallway", "Mail Room",
 "Nook", "Nursery", "Parlor", "Spare Room", "Storeroom"]

#True False
V_Mode = False
day_1 = False
epochs = 1000000
boilerRoomDraftedX2 = True
libraryDraftedX2 = True
tombWallAngelOpen = True
#[0,1,0,0,0, 1,0,1,1,0, 1,1,1,1,1]#common
#[0,1,1,0,0, 1,1,1,1,0, 1,1,1,1,1]#common + standard
#[1,1,1,1,1, 1,1,1,1,1, 1,1,1,1,1]
timesDraftedRoom = [0,0,0,0,0, 0,0,0,0,0, 0,0,0,0,0]#[0,0,0,0,0, 0,0,0,0,0, 0,0,0,0,0]
normalDraftedRequired = [2,5,1,2,1, 0,1,1,0,4, 1,1,2,1,0]

orderRemapNormal = [45,46,47,48,51,52,53,54,55,57,44]
upgradeOrders = [
#day 1
[63],[53],[55],[51],[62],[64],[56],[59],[58],[52],[57],[61],[50],[60],[54],
[13], [3], [5], [1],[12],[14], [6], [9], [8], [2], [7],[11], [0],[10],
#veteran
[14,7,13,10],
[13,2,8,9],
[6,12,13,7,11],
[9,3,7,14],
[3,7,14],
[5,200,12],#check for boiler?
[8,14,10,1],
[2,10,9,3,8,5,7,1,4,12,11,13,6,14],
[12,3,5,8,7],
[1,9,7,6],
[7,14,2,13,4,10,9,3,8,5,1,12,11,0,6],
[11,3,12,4,1,9,2,10,8,5,7,0,13,6,14],
[0,11,3,4],
[10,6,8,5,2,0,8],
[4,12,0,9],
#normal
[111,3,12,4,1,9,2,10,8,5,7,0,13,6],
[13,2,8,109],#check for 9 x 2
[5,150,12],#check for 0 x 2 + boiler
[8,14,10,1],
[106,12,13,7,11],#check for 6 x 1
[150,11,3,4],#check for 0 x 2 + boiler
[107,14,2,13,4,10,9,3,8,5,1,12,11,0,6],
[14,7,13,10],
[154,12,0,9],#check for 4 x 1 + angel door
[160,106,8,5,2,0,8],#checks for 10 x 1 + library, 6 x 1 #hallway is twice here ...
[101,109,7,6],#checks for 1 x 5, 9 x 4
[112,103,5,8,7],#checks for 12 x 2, 3 x 2
[109,3,7,14],#check for 9 x 4
[102,160,109,3,8,5,7,1,4,12,11,0,13,6,14],
#fallback
[14,8,2,3,10,9,5,13,7,1,4,12,11,0,6,14]]

def orderCheck(currOrder):
    for i in upgradeOrders[currOrder]:
        iMod = i%50   
        if i>=50 and i<100:#vet + day1 checks
            if timesDraftedRoom[iMod]>0:
                return -1
        elif i>=100 and i<150:#normal checks
            if timesDraftedRoom[iMod]<normalDraftedRequired[iMod]:
                return -1
        elif i>=150:#normal checks + other conditions
            match i:
                case 150:
                    if not(timesDraftedRoom[iMod]>=normalDraftedRequired[iMod] and boilerRoomDraftedX2):
                        return -1
                case 154:
                    if not(timesDraftedRoom[iMod]>=normalDraftedRequired[iMod] and tombWallAngelOpen):
                        return -1  
                case 160:
                    if not(timesDraftedRoom[iMod]>=normalDraftedRequired[iMod] and libraryDraftedX2):
                        return -1
                case 200:
                    return -1
        if not iMod in pickedRooms:
            return iMod
    return -1

pickedStats = [[0]*15 for _ in range(15)]
for i in range(epochs):
    pickedRooms = set()
    #first pick
    if(not V_Mode):
        picked = random.choices(
            population=[5,14,6,2,10,13,8],
            weights=[0.05,0.35,0.25,0.1,0.05,0.1,0.1],
            k=1
        )[0]
    else:
        picked = random.randint(0,14)  # randint is inclusive
    pickedStats[picked][0] += 1;
    pickedRooms.add(picked)
    
    #other picks 
    for j in range(1,15):
        #first decide upgrade order
        picked = -1
        if(V_Mode):
            if(day_1):
                a = random.random()
                if(a<0.7):#current 70% roll for day 1 checks...
                    order = random.randint(0,14)
                else:
                    order = random.randint(0,14) + 29
            else:
                order = random.randint(0,14) + 29
        else:
            order = random.randint(0,10)
            order = orderRemapNormal[order]
            
        #chained upgrade orders, start from the decided order number
        for k in range(order,59):
            picked = orderCheck(k)
            if picked > -1:
                pickedStats[picked][j]+=1;
                pickedRooms.add(picked)
                break
        #if all failed a random 1 in 15 is picked, I'll skip that to see if any errors pop up
    if i%1000 == 0:
        print(i)
    
#output
for room_index, row in enumerate(pickedStats):
    line = [roomNames[room_index]]
    for count in row:
        percent = (count / epochs) * 100
        line.append(f"{percent:.2f}%")
    print(",".join(line))
    
print("-------------")
for room_index, row in enumerate(pickedStats):
    line = [roomNames[room_index]]
    for count in row:
        percent = count
        line.append(f"{percent}")
    print(",".join(line))
    
print()
input("Done. Press Enter to exit...")