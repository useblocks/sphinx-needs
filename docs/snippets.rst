Snippets
========

.. contents::
   :local:

How to create a pie chart with matplotlib?
------------------------------------------
This example shows the distribution of the different need-types used in this documentation.

.. plot::

   import matplotlib.pyplot as plt
   from matplotlib.sphinxext.plot_directive import setup

   # Get needs data
   needs = setup.app.env.needs_all_needs

   # Calculate numbers from need data
   type_count = {}
   for key, need in needs.items():
      if need['type'] not in type_count.keys():
         type_count[need['type']] = 1
      else:
       type_count[need['type']] += 1

   # Configure  and show matplotlib plot
   labels = type_count.keys()
   sizes = type_count.values()

   fig1, ax1 = plt.subplots()
   ax1.pie(sizes, labels=labels, autopct='%1.1f%%',
        shadow=True, startangle=90)
   ax1.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
   plt.show()

.. warning::

   The used plot-directive from matplotlib gets executed directly before all documents get read in.
   Therefor the available needs will not be correct during plot generation time.

   To avoid this use the sphinx-needs internal plot mechanisms: :ref:`needpie`.

**Installation**::

   pip install matplotlib

**Configuration**::

   # conf.py
   extensions = ['sphinxcontrib.needs', 'matplotlib.sphinxext.plot_directive']


**RST code**::

   This example shows the distribution of the different need-types used in this documentation.

   .. plot::

      # Load matplotlib
      import matplotlib.pyplot as plt

      # Load setup routine, which contains sphinx env, which stores needs data
      from matplotlib.sphinxext.plot_directive import setup

      # Get needs data
      needs = setup.app.env.needs_all_needs

      # Calculate numbers from need data
      type_count = {}
      for key, need in needs.items():
         if need['type'] not in type_count.keys():
            type_count[need['type']] = 1
         else:
          type_count[need['type']] += 1

      # Configure  and show matplotlib plot
      labels = type_count.keys()
      sizes = type_count.values()

      fig1, ax1 = plt.subplots()
      ax1.pie(sizes, labels=labels, autopct='%1.1f%%', shadow=True, startangle=90)
      ax1.axis('equal')
      plt.show()

Read the `plot directive documentation <https://matplotlib.org/3.1.3/devel/plot_directive.html#module-matplotlib.sphinxext.plot_directive>`_
for more information how to use and configure it.

How to create a bar chart with matplotlib?
------------------------------------------
.. plot::

   # Load matplotlib
   import matplotlib.pyplot as plt
   import numpy as np

   # Load setup routine, which contains sphinx env, which stores needs data
   from matplotlib.sphinxext.plot_directive import setup

   from sphinxcontrib.needs.filter_common import filter_needs

   # Prepare plot
   labels = ['Open', 'In progress', 'Closed', 'None / not set']
   x = np.arange(len(labels))  # the label locations
   width = 0.35  # the width of the bars
   fig, ax = plt.subplots()

   # Get needs data
   needs = setup.app.env.needs_all_needs.values()

   need_types = ['req', 'spec', 'impl', 'feature', 'test']
   for index, need_type in enumerate(need_types):
       results = []
       results.append(len(filter_needs(needs, f"type=='{need_type}' and status=='open'")))
       results.append(len(filter_needs(needs, f"type=='{need_type}' and status in ['in_progress', 'in progress']")))
       results.append(len(filter_needs(needs, f"type=='{need_type}' and status in ['done','closed']")))
       results.append(len(filter_needs(needs, f"type=='{need_type}' and status==None")))
       ax.bar(x + width* index, results, width, label=need_type)

   ax.set_ylabel('Amount')
   ax.set_title('Amount of needs by status and type')
   ax.set_xticks(x)
   ax.set_xticklabels(labels)
   ax.legend()

   fig.tight_layout()
   plt.show()

.. warning::

   The used plot-directive from matplotlib gets executed directly before all documents get read in.
   Therefor the available needs will not be correct during plot generation time.

   To avoid this use the sphinx-needs internal plot mechanisms: :ref:`needpie`.

**Installation**::

   pip install matplotlib

**Configuration**::

   # conf.py
   extensions = ['sphinxcontrib.needs', 'matplotlib.sphinxext.plot_directive']


**RST code**::

   .. plot::

      # Load matplotlib
      import matplotlib.pyplot as plt
      import numpy as np

      # Load setup routine, which contains sphinx env, which stores needs data
      from matplotlib.sphinxext.plot_directive import setup

      from sphinxcontrib.needs.filter_common import filter_needs

      # Prepare plot
      labels= ['open', 'in progress', 'closed', 'None']
      x = np.arange(len(labels))  # the label locations
      width = 0.35  # the width of the bars
      fig, ax = plt.subplots()

      # Get needs data
      needs = setup.app.env.needs_all_needs.values()

      need_types = ['req', 'spec', 'impl', 'feature', 'test']
      for index, need_type in enumerate(need_types):
         results = []
         results.append(len(filter_needs(needs, f"type=='{need_type}' and status=='open'")))
         results.append(len(filter_needs(needs, f"type=='{need_type}' and status=='in_progress'")))
         results.append(len(filter_needs(needs, f"type=='{need_type}' and status in ['done','closed']")))
         results.append(len(filter_needs(needs, f"type=='{need_type}' and status==None")))
         ax.bar(x + width* index, results, width, label=need_type)

      ax.set_ylabel('Amount')
      ax.set_title('Amount of needs by status and type')
      ax.set_xticks(x)
      ax.set_xticklabels(labels)
      ax.legend()

      fig.tight_layout()
      plt.show()
