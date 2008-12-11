<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:fo="http://www.w3.org/1999/XSL/Format">
	<xsl:variable name="initial_bottom_pos">24.5</xsl:variable>
	<xsl:variable name="initial_left_pos">1</xsl:variable>
	<xsl:variable name="height_increment">3.8</xsl:variable>
	<xsl:variable name="width_increment">7</xsl:variable>
	<xsl:variable name="frame_height">3.5cm</xsl:variable>
	<xsl:variable name="frame_width">6.5cm</xsl:variable>
	<xsl:variable name="number_columns">3</xsl:variable>
	<xsl:variable name="max_frames">21</xsl:variable>

	<xsl:template match="/">
		<xsl:apply-templates select="lots"/>
	</xsl:template>

	<xsl:template match="lots">
		<document>
			<template leftMargin="2.0cm" rightMargin="2.0cm" topMargin="2.0cm" bottomMargin="2.0cm" title="Address list" author="Generated by Open ERP">
				<pageTemplate id="all">
					<pageGraphics/>
					<xsl:apply-templates select="lot-line" mode="frames"/>
				</pageTemplate>
			</template>
			<stylesheet>
				<paraStyle name="nospace" fontName="Courier" fontSize="10" spaceBefore="0" spaceAfter="0"/>
			</stylesheet>
			<story>
				<xsl:apply-templates select="lot-line" mode="story"/>
			</story>
		</document>
	</xsl:template>

	<xsl:template match="lot-line" mode="frames">
		<xsl:if test="position() &lt; $max_frames + 1">
			<frame>
				<xsl:attribute name="width">
					<xsl:value-of select="$frame_width"/>
				</xsl:attribute>
				<xsl:attribute name="height">
					<xsl:value-of select="$frame_height"/>
				</xsl:attribute>
				<xsl:attribute name="x1">
					<xsl:value-of select="$initial_left_pos + ((position()-1) mod $number_columns) * $width_increment"/>
					<xsl:text>cm</xsl:text>
				</xsl:attribute>
				<xsl:attribute name="y1">
					<xsl:value-of select="$initial_bottom_pos - floor((position()-1) div $number_columns) * $height_increment"/>
					<xsl:text>cm</xsl:text>
				</xsl:attribute>
			</frame>
		</xsl:if>
	</xsl:template>

	<xsl:template match="lot-line" mode="story">
		<para style="nospace"><xsl:value-of select="code"/><xsl:text>, </xsl:text><xsl:value-of select="quantity"/><xsl:text> </xsl:text><xsl:value-of select="uom"/></para>
		<para style="nospace"><xsl:value-of select="product"/><xsl:text> </xsl:text><xsl:value-of select="variant"/></para>
		<para style="nospace">Serial: <xsl:value-of select="serial"/></para>
		<para style="nospace">Tracking: <xsl:value-of select="serial"/></para>
		<spacer length="0.3cm"/>
		<barCode><xsl:value-of select="tracking"/></barCode>
		<nextFrame/>
	</xsl:template>
</xsl:stylesheet>
