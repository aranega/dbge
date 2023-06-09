#include <Python.h>
#include <stdio.h>

#if PY_MAJOR_VERSION == 3

#if PY_MINOR_VERSION == 11
    #include <internal/pycore_frame.h>
    #define STACK(o) (o->f_frame->localsplus)
    #define STACKTOP_IDX(o) (o->f_frame->stacktop)
    #define TOS(o) (STACK(o)[STACKTOP_IDX(o) - 1])
    #define STACK_AT(o, i) (STACK(o)[i])

// #elif PY_MINOR_VERSION == 10
//     #include <pyframe.h>
//     #define STACK(o) (o->f_valuestack)
//     #define STACKTOP_IDX(o) (o->f_stackdepth)
//     #define TOS(o) (STACK(o)[STACKTOP_IDX(o) - 1])
//     #define STACK_AT(o, i) (STACK(o)[i])

// #elif PY_MINOR_VERSION == 9
//     #include <frameobject.h>
//     #define STACK(o) (*o->f_valuestack)
//     #define TOS(o) (*o->f_stacktop)
//     #define STACKTOP_IDX(o) (o->f_stacktop - o->f_valuestack)
//     #define STACK_AT(o, i) (o->f_valuestack[i])

// #elif PY_MINOR_VERSION == 8
//     #define STACK(o) (o->f_valuestack)
//     #define TOS(o) (o->f_stacktop)
//     #define STACKTOP_IDX(o) (TOS(o) - STACK(o))
//     #define STACK_AT(o, i) (STACK(o)[i])

// #elif PY_MINOR_VERSION == 7
//     #define STACK(o) (o->f_valuestack)
//     #define TOS(o) (o->f_stacktop)
//     #define STACKTOP_IDX(o) (TOS(o) - STACK(o))
//     #define STACK_AT(o, i) (STACK(o)[i])

#endif
#endif

static inline PyObject * convert_weak(PyObject *obj)
{
    if (obj == NULL) {
        // return Py_BuildValue("s", "(nil)");
        return Py_BuildValue("");
    }
    PyObject *weakref = PyWeakref_NewRef(obj, NULL);
    PyErr_Clear();
    return weakref == NULL ? obj : weakref;
}

static PyObject *frame_stack_at(PyObject *self, PyObject *args)
{
    PyFrameObject *frame;
    int index = 0;
    if (!PyArg_ParseTuple(args, "Oi", &frame, &index)) {
        return NULL;
    }
    return convert_weak(STACK_AT(frame, index));
}

static PyObject *frame_topstack(PyObject *self, PyObject *pyframe)
{
    PyFrameObject *frame = (PyFrameObject *)pyframe;
    return PyLong_FromLong(STACKTOP_IDX(frame));
}

static PyObject *frame_peek_topstack(PyObject *self, PyObject *pyframe)
{
    PyFrameObject *frame = (PyFrameObject *)pyframe;
    PyObject *res = TOS(frame);
    return convert_weak(res);
}

static PyObject *frame_change_topstack(PyObject *self, PyObject *args)
{
    PyFrameObject *frame;
    PyObject *value;
    if (!PyArg_ParseTuple(args, "OO", &frame, &value)) {
        return NULL;
    }
    TOS(frame) = value;
    return value;
}

// Defines the methods of the extension
static PyMethodDef frame_access_methods[] = {
    {"stack_at", frame_stack_at, METH_VARARGS, "Returns a weakref (if possible) towards the value at an index in the internal frame stack. If the value at the index is not weakreferenceable, the actual value is returned."},
    {"topstack", frame_topstack, METH_O, "Returns a the stack top value of the internal frame."},
    {"peek_topstack", frame_peek_topstack, METH_O, "Returns a weak reference (if possible) towards the TOS (Top Of the Stack) of the internal evaluation stack. If the TOS is not weakreferenceable, the actual TOS is returned."},
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