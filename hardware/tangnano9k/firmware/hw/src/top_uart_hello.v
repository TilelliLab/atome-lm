module top_uart_hello (
    input clk_27,
    input btnL,

    output [5:0] led_n,
    input uart_rx,
    output uart_tx
);
    reg [15:0] reset_counter = 16'd0;
    reg por_done = 1'b0;

    always @(posedge clk_27) begin
        if (!btnL) begin
            reset_counter <= 16'd0;
            por_done <= 1'b0;
        end else if (!por_done) begin
            reset_counter <= reset_counter + 16'd1;
            por_done <= &reset_counter;
        end
    end

    wire resetn = btnL && por_done;

    wire iomem_valid;
    wire [3:0] iomem_wstrb;
    wire [31:0] iomem_addr;
    wire [31:0] iomem_wdata;
    reg iomem_ready;
    reg [31:0] iomem_rdata;

    wire [31:0] ram_data = 32'h0000_0000;
    wire [31:0] ram_addr = 32'h0000_0000;
    wire progmem_wen = 1'b0;

    reg [25:0] blink_counter;
    reg [31:0] timer_counter;
    reg timer_irq_enable;
    reg timer_irq_pending;
    reg [31:0] timer_irq_period;
    reg [31:0] timer_irq_countdown;
    reg [31:0] timer_irq_event_count;
    reg        soft_irq;   // FreeRTOS yield: software-triggered interrupt on irq_6

    wire timer_en = iomem_valid && (iomem_addr[31:24] == 8'h03);

    always @(posedge clk_27) begin
        if (!resetn) begin
            blink_counter <= 26'd0;
            timer_counter <= 32'd0;
            timer_irq_enable <= 1'b0;
            timer_irq_pending <= 1'b0;
            timer_irq_period <= 32'd2700000;
            timer_irq_countdown <= 32'd2700000;
            timer_irq_event_count <= 32'd0;
            soft_irq <= 1'b0;
            iomem_ready <= 1'b0;
            iomem_rdata <= 32'h0000_0000;
        end else begin
            blink_counter <= blink_counter + 26'd1;
            timer_counter <= timer_counter + 32'd1;
            iomem_ready <= 1'b0;
            soft_irq <= 1'b0;   // one-cycle pulse only; picorv32 latches irq_6

            if (timer_irq_enable && !timer_irq_pending) begin
                if (timer_irq_countdown == 32'd0) begin
                    timer_irq_pending <= 1'b1;
                    timer_irq_event_count <= timer_counter;
                    timer_irq_countdown <= timer_irq_period;
                end else begin
                    timer_irq_countdown <= timer_irq_countdown - 32'd1;
                end
            end

            if (timer_en && !iomem_ready) begin
                iomem_ready <= 1'b1;

                case (iomem_addr[4:2])
                    3'b000: iomem_rdata <= timer_counter;
                    3'b001: iomem_rdata <= 32'd27000000;
                    3'b010: iomem_rdata <= {31'd0, timer_irq_enable};
                    3'b011: iomem_rdata <= {31'd0, timer_irq_pending};
                    3'b100: iomem_rdata <= timer_irq_period;
                    3'b101: iomem_rdata <= timer_irq_countdown;
                    3'b110: iomem_rdata <= timer_irq_event_count;
                    default: iomem_rdata <= 32'h0000_0000;
                endcase

                if (iomem_wstrb != 4'b0000) begin
                    case (iomem_addr[4:2])
                        3'b000: timer_counter <= iomem_wdata;
                        3'b010: timer_irq_enable <= iomem_wdata[0];
                        3'b011: begin
                            if (iomem_wdata[0]) begin
                                timer_irq_pending <= 1'b0;
                            end
                        end
                        3'b100: begin
                            timer_irq_period <= iomem_wdata;
                            timer_irq_countdown <= iomem_wdata;
                        end
                        3'b111: begin
                            // 0x0300001C: write 1 -> pulse irq_6 (FreeRTOS yield)
                            soft_irq <= iomem_wdata[0];
                        end
                        default: begin
                        end
                    endcase
                end
            end
        end
    end

    assign led_n[0] = ~blink_counter[24];
    assign led_n[1] = uart_tx;
    assign led_n[5:2] = 4'b1111;

    picosoc_noflash soc (
        .clk(clk_27),
        .resetn(resetn),

        .ser_tx(uart_tx),
        .ser_rx(uart_rx),

        .irq_5(timer_irq_pending),
        .irq_6(soft_irq),
        .irq_7(1'b0),

        .iomem_valid(iomem_valid),
        .iomem_ready(iomem_ready),
        .iomem_wstrb(iomem_wstrb),
        .iomem_addr(iomem_addr),
        .iomem_wdata(iomem_wdata),
        .iomem_rdata(iomem_rdata),

        .progmem_wen(progmem_wen),
        .progmem_waddr(ram_addr),
        .progmem_wdata(ram_data)
    );
endmodule
