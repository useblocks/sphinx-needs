Domains
=======

.. py:module:: pkg.mod

.. py:class:: Klass

   .. py:method:: meth(x)

      .. req:: in py method
         :id: REQ_PYMX

   .. req:: in py class
      :id: REQ_PYCX

.. py:function:: func()

   .. req:: in py func
      :id: REQ_PYFX

.. py:function:: other.qual.func2()

   .. req:: in qualified py func
      :id: REQ_PYQX

.. c:function:: int cfunc(int a)

   .. req:: in c func
      :id: REQ_CFX

.. c:struct:: cstruct

   .. c:member:: int field

      .. req:: in c member
         :id: REQ_CMX

.. cpp:namespace:: ns

.. cpp:class:: Widget

   .. cpp:function:: void run(int)

      .. req:: in cpp method
         :id: REQ_CPPMX

.. cpp:namespace:: 0

.. js:module:: jsmod

.. js:class:: JsKlass

   .. js:method:: go()

      .. req:: in js method
         :id: REQ_JSMX

.. rst:directive:: .. mydir::

   .. rst:directive:option:: opt

      .. req:: in rst option
         :id: REQ_RSTOX

.. option:: --verbose

   .. req:: in std option
      :id: REQ_STDOX

.. envvar:: MYVAR

   .. req:: in envvar
      :id: REQ_ENVX

.. py:function:: f_a()
                 f_b()

   .. req:: in multi-sig py func
      :id: REQ_MULTIX

Sub section
-----------

.. req:: in subsection after domains
   :id: REQ_SUBX

.. req:: parent need
   :id: REQ_PARX

   .. req:: child need
      :id: REQ_CHILDX

.. py:function:: noindex_f()
   :no-index:

   .. req:: in noindex func
      :id: REQ_NOIDXX
