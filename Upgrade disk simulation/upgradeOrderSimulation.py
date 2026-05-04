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
#15 "Spare Room 2"

roomNames = ["Aquarium", "Billiard Room", "Boudoir", "Bunk Room", "Cloister",
 "Closet", "Courtyard", "Guest Bedroom", "Hallway", "Mail Room",
 "Nook", "Nursery", "Parlor", "Spare Room", "Storeroom", "Spare Room 2"]

#True False
V_Mode = True
epochs = 1000000
aquariumDraftedX1 = False
boilerRoomDraftedX2 = False
mailroomDraftedX2 = False
cloisterDraftedX1 = False
tombWallAngelOpen = False

orderRemapNormal = [2,3,4,5,8,9,10,11,12,14,1]
orderRemapVeteran = [9,7,13,0,1,-1,-1]
upgradeOrders = [[4,12,3,9,11,2,10,8,5,7,1,0,13,6,14],
[11,3,12,4,1,9,2,10,8,5,7,0,13,6,15,14],
[13,2,8,59],#check for 9
[5,50,12],#check for 0
[8,14,10,1],
[6,12,13,7,15,11],
[50,11,3,4],#check for 0
[7,14,2,13,15,4,10,9,3,8,5,1,12,11,0,6],
[14,7,13,15,10],
[54,12,0,9],#check for 4
[10,6,8,5,2,0,8],#8 is twice here for no reason
[59,1,7,6],#check for 9 #9 and 1 in wrong order here by mistake?
[12,3,5,8,7],
[9,3,7,14],
[2,10,9,3,8,5,7,1,4,12,11,0,13,6,14,15]]

def orderCheck(currOrder):
    for i in upgradeOrders[currOrder]:
        if i >= 50:
            match i:
                case 50:
                    if not(boilerRoomDraftedX2 and aquariumDraftedX1):
                        return -1
                case 54:
                    if not(tombWallAngelOpen and cloisterDraftedX1):
                        return -1
                case 59:
                    if not(mailroomDraftedX2):
                        return -1
        iMod = i%50               
        if not iMod in pickedRooms:
            return iMod
    return -1

pickedStats = [[0]*16 for _ in range(16)]
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
    for j in range(1,16):
        #first decide upgrade order
        picked = -1
        if(V_Mode):
            order = random.randint(0,6)
            if order > 4:#random chance to fall into normal mode pick
                order = random.randint(0,10)
                order = orderRemapNormal[order]
            else:
                order = orderRemapVeteran[order]
        else:
            order = random.randint(0,10)
            order = orderRemapNormal[order]
            
        #chained upgrade orders, start from the decided order number
        for k in range(order,15):
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