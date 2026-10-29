Domain signatures
=================

.. c:function:: int cfunc(int a)

   .. spec:: In a C function
      :id: SIG_C

.. cpp:namespace:: ns

.. cpp:function:: void run()

   .. spec:: In a C++ function
      :id: SIG_CPP

.. cpp:function:: template<typename X> void tmpl(X x)

   .. spec:: In a C++ function template
      :id: SIG_CPP_TMPL

.. cpp:namespace:: 0

.. js:method:: go()

   .. spec:: In a JavaScript method
      :id: SIG_JS

.. py:class:: Klass

   .. py:method:: meth(self)

      .. spec:: In a Python method
         :id: SIG_PY

.. rst:directive:: .. foo::

   .. rst:directive:option:: opt

      .. spec:: In a directive option
         :id: SIG_RST

.. cpp:function:: void first(int)
                  void second(double)

   .. spec:: In a C++ function with two signatures
      :id: SIG_CPP_TWO

.. py:class:: Host

   .. cpp:function:: void inner()

      .. spec:: In a C++ function inside a Python class
         :id: SIG_CPP_IN_PY

.. nameless:: anything

   .. spec:: In an object whose name is empty
      :id: SIG_EMPTY
