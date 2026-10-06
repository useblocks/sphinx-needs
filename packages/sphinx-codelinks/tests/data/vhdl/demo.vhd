-- demo.vhd

library ieee;
use ieee.std_logic_1164.all;

-- @Counter entity definition, counter_entity, impl, [REQ_001]
entity counter is
  port (
    clk : in std_logic;
    rst : in std_logic
  );
end entity counter;

/* Block comment with marker
   @Counter RTL architecture, counter_arch, impl, [REQ_002]
*/
architecture rtl of counter is
  -- @Counter state type, counter_state, impl, [REQ_003]
  type state_t is (IDLE, RUNNING);
begin
  -- @Counter main process, counter_proc, impl, [REQ_004]
  main_proc : process (clk)
  begin
  end process main_proc;
end architecture rtl;
