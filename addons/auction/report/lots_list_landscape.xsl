<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:fo="http://www.w3.org/1999/XSL/Format">
	<xsl:template match="/">
		<xsl:apply-templates select="lots"/>
	</xsl:template>

	<xsl:template match="lots">
		<document xmlns:fo="http://www.w3.org/1999/XSL/Format">
			<template leftMargin="2.0cm" rightMargin="2.0cm" topMargin="2.0cm" bottomMargin="2.0cm" title="" author="Generated by Open ERP" allowSplitting="20" pageSize="29.7cm,21cm">

				<pageTemplate id="all">
					<pageGraphics/>
					<frame id="list" x1="1.0cm" y1="1.0cm" width="27.7cm" height="19cm"/>
				</pageTemplate>
			</template>

			<stylesheet>
				<paraStyle name="small" fontName="Courier" fontSize="12" spaceBefore="0mm" spaceAfter="0mm"/>
				<paraStyle name="verysmall" fontSize="11" fontName="Courier" spaceBefore="0mm" spaceAfter="0mm"/>
				<paraStyle name="smallest" fontSize="10" fontName="Courier" spaceBefore="-0.5mm" spaceAfter="-0.5mm"/>

				<blockTableStyle id="left">
					<blockValign value="TOP"/>
					<blockAlignment value="LEFT"/>
					<blockFont name="Helvetica-Bold" size="10"/>
					<blockTextColor colorName="black"/>
					<lineStyle kind="LINEABOVE" thickness="0.5" colorName="black" start="0,0" stop="-1,0"/>
					<lineStyle kind="LINEBELOW" thickness="0.5" colorName="black"/>
					<blockBackground colorName="(1,1,1)" start="0,0" stop="-1,-1"/>
					<blockBackground colorName="(0.88,0.88,0.88)" start="0,0" stop="-1,0"/>
				</blockTableStyle>
			</stylesheet>

			<story>
				<blockTable repeatRows="1" style="left" colWidths="1.3cm,11.0cm,2.3cm,1.6cm,6.5cm,2.3cm,2cm">
					<tr>
						<td>
							<para style="small"><b t="1">Cat. N.</b></para>
						</td><td>
							<para style="small"><b t="1">Description</b></para>
						</td><td>
							<para style="small"><b t="1">Est.</b></para>
						</td><td>
							<para style="small"><b t="1">Limit</b></para>
						</td><td>
							<para style="small"><b t="1">Orders</b></para>
						</td><td>
							<para style="small"><b t="1">Inv, Name</b></para>
						</td><td>
							<para style="small"><b t="1">Buyer, Price</b></para>
						</td>
					</tr>
					<xsl:apply-templates select="lot"/>
				</blockTable>
			</story>
		</document>
	</xsl:template>

	<xsl:template match="lot">
		<tr>
			<td>
				<para style="verysmall"><xsl:value-of select="lot_num"/></para>
			</td><td>
				<para style="verysmall"><b><xsl:value-of select="artist"/></b></para>
				<para style="verysmall"><b><xsl:value-of select="lot_desc0"/></b></para>
				<para style="verysmall"><xsl:value-of select="lot_desc"/></para>
			</td><td>
				<para style="verysmall">
					<xsl:if test="lot_est1 != ''">
						<xsl:value-of select="round(lot_est1)"/>
					</xsl:if>
					<xsl:text>-</xsl:text>
					<xsl:if test="lot_est2 != ''">
						<xsl:value-of select="round(lot_est2)"/>
					</xsl:if>
				</para>
			</td><td>
				<xsl:if test="lot_limit != ''">
					<para style="verysmall">
						<b><xsl:value-of select="round(lot_limit)"/></b>
					</para>
				</xsl:if>
				<xsl:if test="lot_limit_net != ''">
					<para style="verysmall">
						<b t="1">NET</b>
					</para>
				</xsl:if>
			</td><td>
				<xsl:for-each select="bid">
					<xsl:sort order="descending" data-type="number" select="bid_prix"/>
					<para style="smallest">
						<xsl:choose>
							<xsl:when test="bid_tel_ok='1'">
								<b t="1">TEL:</b>
							</xsl:when>
							<xsl:otherwise t="1">
								BID:
							</xsl:otherwise>
						</xsl:choose>
						<xsl:value-of select="bid_name"/>
						<xsl:text>(</xsl:text><xsl:value-of select="bid_id"/><xsl:text>)</xsl:text>
						<xsl:if test="round(bid_prix)&gt;0">
							<xsl:text> </xsl:text><b><xsl:value-of select="round(bid_prix)"/><xsl:text> EUR</xsl:text></b>
						</xsl:if>
						<xsl:if test="bid_tel_ok='1'">
							<b><xsl:text t="1">, TEL:</xsl:text><xsl:value-of select="bid_tel"/></b>
						</xsl:if>
					</para>
				</xsl:for-each>
			</td><td>
				<para style="verysmall">
					<xsl:value-of select="deposit_num"/>
					<xsl:text> </xsl:text><xsl:value-of select="substring(lot_seller_ref,0,5)"/>
					<xsl:text> </xsl:text><xsl:value-of select="substring(lot_seller,0,9)"/>
				</para>
			</td><td>
				<para style="verysmall">
					<xsl:value-of select="buyer_login"/>
					<xsl:if test="obj_price &gt; 0">
						<xsl:text>, </xsl:text>
						<xsl:value-of select="obj_price"/>
					</xsl:if>
				</para>
			</td>
		</tr>
	</xsl:template>
</xsl:stylesheet>
