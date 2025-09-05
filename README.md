A place to store Blue Prine related stuff.
folders:
Datamine scripts:
Not made by me, but donated by an anonymous person, thank you.

The FindGemsInTheDataMine.py script goes through all the objects inside Mount Holly Estate.unity and GameObject/*.prefab files and outputs a big csv file. The script has some additional options of filtering out objects to output based on names of stuff in the object tree path that you can edit yourself. It's well commented on why some stuff is done the way it is. I guess you could modify it a little and reuse on any Unity game that you export with AssetRipper.

I think it originally started just as a dump to look for objects that interact with the player or generally send events to each other and stuff like that (m_IsTrigger column = 1). But after my requests more and more columns were added so I can quickly search and filter out some things I wanted to see like FSM states and events, Animator and Audio components.

The other script CreateGUIDMapping.py creates a .json file so the first script can map GUIDs of content files to their normal readable file names.

Usage: 
0. Preferably close the Unity project if you have it open so it doesn't start auto-importing files from the directory.
1. Put the scripts into the /Assets folder of the exported project.
2. (optional) Run CreateGUIDMapping.py to guid_to_asset.json for GUID mappings.
3. Run FindGemsInTheDataMine.py to create the_white_print.csv.
4. Open the_white_print.csv and read.

I recommed putting it into Excel or something and order it by the 1st column and make filters on the columns to see just what you want to. Maybe an interesting thing for more casual viewing is filtering out where the m_text column is not empty. A lot will probably still be meaningless. Then you can compare texts in room objects to the real texts that are shown when you click on the document under .../UI Documents/DOCUMENTS/...
