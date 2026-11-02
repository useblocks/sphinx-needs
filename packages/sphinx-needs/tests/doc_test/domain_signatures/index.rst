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

.. py:class:: Outer

   .. nameless:: anything

      .. spec:: In an object whose name is empty, inside a Python class
         :id: SIG_EMPTY_IN_PY

.. outside-signature::

   .. spec:: After a signature outside any domain object
      :id: SIG_OUTSIDE

.. spec:: A need holding a Python function
   :id: SIG_NEED_OUTER

   .. py:function:: in_need()

      .. spec:: In a Python function inside a need
         :id: SIG_PY_IN_NEED

         .. spec:: In a need inside that need
            :id: SIG_PY_IN_NEED_CHILD
