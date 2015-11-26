Export an animated model from Blender 2.6x to Cal3D with extra features

My main objective is to provide finer control over a rigged exportation than usual exporter.
Feel free to report bugs.
Further this exporter is someway designed to deal with complex model with multiple armatures (such as the Miku example)....if you experience problems, consider using a more "regular" exporter


## Main Features: ##
  1. Dependant armatures merging in one single skeleton
  1. Weight threshold based bone elimination (poorly expressed bones removal)
  1. Weight threshold based vertex influences elimination (poorly weighted vertex influences removal)
  1. Interactive bones removal via virtual armature editing

## How to use: ##
  * Pack the Cal3DExporter directory to zip
  * Add it as blender addons
  * See next steps in the wiki



## TODO: ##
  * Intermediate unexpressed bone removal (a bone need all its children to be unexpressed to be removed ...so need to developp a bone "shunter" feature IYSWIM )
  * Clean and improve keyframes export (take into account more bone constraints)
  * A lot of others cal3d related stuff to check/debug (Level of Detail, Spring System...)

## Known Bugs: ##
  * **Blender World Transform is not apply to meshes so set it to identity**
  * **Binary export bug under linux?!**
  * Global variables are not purged (reboot Blender to avoid bugs)
  * Bug with maximum weight parameter (debug code or let it 0)
  * Virtual armature is not visually correct in some cases (matrix bug)
  * Non Interactive mode seams to fail in some cases



|Sample exported model|
|:--------------------|
|<a href='http://www.youtube.com/watch?feature=player_embedded&v=On67mVoN5pw' target='_blank'><img src='http://img.youtube.com/vi/On67mVoN5pw/0.jpg' width='425' height=344 /></a>|


### Character animation instancing with a baked model ###
![http://blender2cal3d-exporter.googlecode.com/svn/svn/MultiMikuBlendShapes.png](http://blender2cal3d-exporter.googlecode.com/svn/svn/MultiMikuBlendShapes.png)