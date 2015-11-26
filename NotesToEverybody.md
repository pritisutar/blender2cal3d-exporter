# Blender2Cal3dExporter #

This project aim to provide Blender 2.6x an exporter in order to export animated model into Cal3d format

Not really work well for Miku model's fingers but it's automatic...



## How to use ##
  1. Go in object mode (check to Matrix World Transform has no scale or rotation)
  1. Select BOTH meshes and armatures to export (savin at this point can be a good idea)
  1. File->export->Cal3D(.cfg)
  1. A temporary skeleton is generated so go remove bones you don't want
  1. return to Object Mode and right click on the original model to continue the export.

## Where to find Cal3d library ##
Cal3d is mandatory if you want to test results. It can be found here:
[Cal3D HomePage](http://gna.org/projects/cal3d/) (use the svn version for correct blendshape support)