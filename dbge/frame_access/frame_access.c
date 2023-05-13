#include <Python.h>
#include <stdio.h>

#if PY_MAJOR_VERSION == 3

#if PY_MINOR_VERSION == 11
    #include <internal/pycore_frame.h>
    #define STACK(o) (o->f_frame->localsplus)
    #define STACKTOP_IDX(o) (o->f_frame->stacktop)
    #define STACKTOP(o) (STACK(o)[STACKTOP_IDX(o) - 1])
    #define STACK_AT(o, i) (STACK(o)[i])

// #elif PY_MINOR_VERSION == 10
//     #include <pyframe.h>
//     #define STACK(o) (o->f_valuestack)
//     #define STACKTOP_IDX(o) (o->f_stackdepth)
//     #define STACKTOP(o) (STACK(o)[STACKTOP_IDX(o) - 1])
//     #define STACK_AT(o, i) (STACK(o)[i])

// #elif PY_MINOR_VERSION == 9
//     #include <frameobject.h>
//     #define STACK(o) (*o->f_valuestack)
//     #define STACKTOP(o) (*o->f_stacktop)
//     #define STACKTOP_IDX(o) (o->f_stacktop - o->f_valuestack)
//     #define STACK_AT(o, i) (o->f_valuestack[i])

// #elif PY_MINOR_VERSION == 8
//     #define STACK(o) (o->f_valuestack)
//     #define STACKTOP(o) (o->f_stacktop)
//     #define STACKTOP_IDX(o) (STACKTOP(o) - STACK(o))
//     #define STACK_AT(o, i) (STACK(o)[i])

// #elif PY_MINOR_VERSION == 7
//     #define STACK(o) (o->f_valuestack)
//     #define STACKTOP(o) (o->f_stacktop)
//     #define STACKTOP_IDX(o) (STACKTOP(o) - STACK(o))
//     #define STACK_AT(o, i) (STACK(o)[i])

#endif
#endif

static PyObject *frame_stack_at(PyObject *self, PyObject *args)
{
    PyFrameObject *frame;
    int index = 0;
    if (!PyArg_ParseTuple(args, "Oi", &frame, &index)) {
        return NULL;
    }
    PyObject *res = STACK_AT(frame, index);
    // Py_XINCREF(res);
    return !res ? Py_BuildValue("") : res;
}

static PyObject *frame_topstack(PyObject *self, PyObject *pyframe)
{
    PyFrameObject *frame = (PyFrameObject *)pyframe;
    return PyLong_FromLong(STACKTOP_IDX(frame));
}

static PyObject *frame_peek_topstack(PyObject *self, PyObject *pyframe)
{
    PyFrameObject *frame = (PyFrameObject *)pyframe;
    PyObject *res = STACKTOP(frame);
    // Py_XINCREF(res);  // This probably introduces a memory leak
    return !res ? Py_BuildValue("") : res;
}

// static PyObject *frame_decrease(PyObject *self, PyObject *obj)
// {
//     Py_XDECREF(obj);
//     return Py_BuildValue("");
// }

static PyObject *frame_change_topstack(PyObject *self, PyObject *args)
{
    PyFrameObject *frame;
    PyObject *value;
    if (!PyArg_ParseTuple(args, "OO", &frame, &value)) {
        return NULL;
    }
    STACKTOP(frame) = value;
    return value;
}

// Defines the methods of the extension
static PyMethodDef frame_access_methods[] = {
    {"stack_at", frame_stack_at, METH_VARARGS, "Returns internal frame stack index."},
    {"topstack", frame_topstack, METH_O, "Returns the stack top value of the internal frame."},
    {"peek_topstack", frame_peek_topstack, METH_O, "Returns the value at the internal frame stack top."},
    // {"decrease", frame_decrease, METH_O, "Release the stack top."},
    {"change_topstack", frame_change_topstack, METH_VARARGS, "Alter the top of the internal frame stack."},
    {NULL, NULL, 0, NULL}
};

// Defines the extention in itself
static struct PyModuleDef frame_access_module = {
    PyModuleDef_HEAD_INIT,
    "frame_access",
    "Give extended access to the FrameObject",
    -1,
    frame_access_methods
};

PyMODINIT_FUNC PyInit_frame_access(void) {
    return PyModule_Create(&frame_access_module);
}