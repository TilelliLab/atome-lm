module simpleuart (
	input clk,
	input resetn,

	output ser_tx,
	input ser_rx,

	input [3:0] reg_div_we,
	input [31:0] reg_div_di,
	output [31:0] reg_div_do,

	input reg_dat_we,
	input reg_dat_re,
	input [31:0] reg_dat_di,
	output [31:0] reg_dat_do,
	output reg_dat_wait
);
	reg [31:0] cfg_divider;

	reg [31:0] tx_divcnt;
	reg [3:0] tx_bitcnt;
	reg [9:0] tx_shift;
	reg tx_busy;

	reg [31:0] rx_divcnt;
	reg [3:0] rx_bitcnt;
	reg [7:0] rx_shift;
	reg [7:0] rx_data;
	reg rx_busy;
	reg rx_valid;

	wire [31:0] active_divider = cfg_divider == 0 ? 32'd1 : cfg_divider;
	wire tx_start = reg_dat_we && !tx_busy;

	assign reg_div_do = cfg_divider;
	assign reg_dat_do = rx_valid ? {24'h000000, rx_data} : 32'h00000000;
	assign reg_dat_wait = reg_dat_we && tx_busy;
	assign ser_tx = tx_busy ? tx_shift[0] : 1'b1;

	always @(posedge clk) begin
		if (!resetn) begin
			cfg_divider <= 32'd562;
		end else begin
			if (reg_div_we[0]) cfg_divider[7:0] <= reg_div_di[7:0];
			if (reg_div_we[1]) cfg_divider[15:8] <= reg_div_di[15:8];
			if (reg_div_we[2]) cfg_divider[23:16] <= reg_div_di[23:16];
			if (reg_div_we[3]) cfg_divider[31:24] <= reg_div_di[31:24];
		end
	end

	always @(posedge clk) begin
		if (!resetn) begin
			tx_busy <= 1'b0;
			tx_divcnt <= 32'd0;
			tx_bitcnt <= 4'd0;
			tx_shift <= 10'h3ff;
		end else if (tx_start) begin
			tx_busy <= 1'b1;
			tx_divcnt <= active_divider;
			tx_bitcnt <= 4'd0;
			tx_shift <= {1'b1, reg_dat_di[7:0], 1'b0};
		end else if (tx_busy) begin
			if (tx_divcnt != 0) begin
				tx_divcnt <= tx_divcnt - 1;
			end else begin
				tx_divcnt <= active_divider;
				tx_shift <= {1'b1, tx_shift[9:1]};

				if (tx_bitcnt == 4'd9) begin
					tx_busy <= 1'b0;
					tx_bitcnt <= 4'd0;
				end else begin
					tx_bitcnt <= tx_bitcnt + 1;
				end
			end
		end
	end

	always @(posedge clk) begin
		if (!resetn) begin
			rx_busy <= 1'b0;
			rx_valid <= 1'b0;
			rx_divcnt <= 32'd0;
			rx_bitcnt <= 4'd0;
			rx_shift <= 8'h00;
			rx_data <= 8'h00;
		end else begin
			if (reg_dat_re) begin
				rx_valid <= 1'b0;
			end

			if (!rx_busy && !rx_valid && !ser_rx) begin
				rx_busy <= 1'b1;
				rx_divcnt <= active_divider + (active_divider >> 1);
				rx_bitcnt <= 4'd0;
			end else if (rx_busy) begin
				if (rx_divcnt != 0) begin
					rx_divcnt <= rx_divcnt - 1;
				end else begin
					rx_divcnt <= active_divider;

					if (rx_bitcnt < 4'd8) begin
						rx_shift <= {ser_rx, rx_shift[7:1]};
						rx_bitcnt <= rx_bitcnt + 1;
					end else begin
						rx_data <= rx_shift;
						rx_valid <= 1'b1;
						rx_busy <= 1'b0;
					end
				end
			end
		end
	end
endmodule
