SECTIONS {
  .text : { *(.padstart) *(.text .text.*) *(.rodata .rodata.*) *(.padtail) }
  /DISCARD/ : { *(.comment) *(.eh_frame) *(.note*) *(.sdata*) *(.sbss*) *(.data*) *(.bss*) *(.gnu.attributes) }
}
