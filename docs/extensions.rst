Further Extensions
==================

Most Sphinx extensions are playing well with Sphinx-Needs, but some other are not.

This pages provides some workarounds to get problematic extensions to work with Sphinx-Needs.

Esbonio
-------

`Esbonio <https://github.com/swyddfa/esbonio>`__ runs Sphinx for you automatically and provides
previews and language feature support in VS Code.

However, it does some dirty hacks and keeps all Sphinx data alive between all the different Sphinx builds,
so that an extension must be desiged to be more or less stateless to work with this approach. 

This is not the case for Sphinx-Needs, and some flags need to be reset after a build to allow the next execution.
But this can be done by some extra lines of code in your ``conf.py`` file:

.. code-block:: python
   
   def setup(app: Sphinx):
       app.connect("env-before-read-docs", reset_sphinx_needs_for_esbonio)
       checks.add_warnings(app)

   def reset_sphinx_needs_for_esbonio(_app: Sphinx, env, _documents):
       """ See https://github.com/useblocks/sphinx-needs/issues/1350 """
       # sphinx-needs 2.1.0
       if hasattr(env, "needs_warnings_executed"):
           env.needs_warnings_executed = False

       # sphinx-needs 4.1.0
       if hasattr(env, "_needs_warnings_executed"):
           env._needs_warnings_executed = False

       # sphinx-needs 4.1.0
       if hasattr(env, "_needs_is_post_processed"):
           env._needs_is_post_processed = False

Based on the discussion in `GitHub issues 1350 <https://github.com/useblocks/sphinx-needs/issues/1350>`__