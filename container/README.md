# The RDO toolbox

This toolbox contains the tools suite to
build a new RDO release and more.

It's served at https://quay.io/repository/rdoinfra/rdo-toolbox

# How to use it

You must have [toolbox](https://github.com/containers/toolbox) package installed as prerequisite

```
podman pull quay.io/rdoinfra/rdo-toolbox
# or
docker pull quay.io/rdoinfra/rdo-toolbox

toolbox create -i quay.io/rdoinfra/rdo-toolbox
toolbox enter rdo-toolbox
```
