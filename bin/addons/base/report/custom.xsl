<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:fo="http://www.w3.org/1999/XSL/Format">

<xsl:template match="/">
	<xsl:apply-templates select="report"/>
</xsl:template>

<xsl:template match="report">
	<document filename="example_5.pdf">
	<template leftMargin="1.5cm" rightMargin="1.5cm" topMargin="1.5cm" bottomMargin="1.5cm"
            title="Reporting" author="Generated by OpenERP, Fabien Pinckaers">
		<xsl:attribute name="pageSize">
			<xsl:value-of select="/report/config/pageSize"/>
		</xsl:attribute> 
		<pageTemplate id="first">
			<pageGraphics>
				<drawCentredString>
					<xsl:attribute name="x">
						<xsl:value-of select="/report/config/pageWidth div 2"/>
					</xsl:attribute>
					<xsl:attribute name="y">
						<xsl:value-of select="/report/config/pageHeight - 56.69"/>
					</xsl:attribute>
					<xsl:value-of select="config/report-header"/>
				</drawCentredString>

				<fill color="(0.2,0.2,0.2)"/>
				<setFont name="Helvetica" size="10"/>
				<drawCentredString y="10mm">
					<xsl:attribute name="x">
						<xsl:value-of select="/report/config/pageWidth div 2"/>
					</xsl:attribute>
					<xsl:value-of select="config/report-footer"/>
				</drawCentredString>

				<fill color="(0.969,0.2,0.2)"/>
				<setFont name="Helvetica" size="8"/>
				<drawString x="1.5cm">
					<xsl:attribute name="y">
						<xsl:value-of select="/report/config/pageHeight - 56.69"/>
					</xsl:attribute><xsl:text>OpenERP</xsl:text>
				</drawString>

				<fill color="(0.2,0.2,0.2)"/>
				<drawRightString>
					<xsl:attribute name="x">
						<xsl:value-of select="/report/config/pageWidth - 45"/>
					</xsl:attribute>
					<xsl:attribute name="y">
						<xsl:value-of select="/report/config/pageHeight - 56.69"/>
					</xsl:attribute><xsl:value-of select="/report/config/date"/>
				</drawRightString>
			</pageGraphics>
			<frame id="column" x1="1.5cm" y1="1.5cm">
				<xsl:attribute name="width">
					<xsl:value-of select="/report/config/pageWidth - 85"/>
				</xsl:attribute> 
				<xsl:attribute name="height">
					<xsl:value-of select="/report/config/pageHeight - 100"/>
				</xsl:attribute> 
			</frame>
		</pageTemplate>
	</template>
	<stylesheet>
		<paraStyle name="sum" fontName="Helvetica" textColor="green"/>
		<paraStyle name="sum_float" fontName="Helvetica" alignment="right" textColor="green"/>
		<paraStyle name="sum_end" fontName="Helvetica" textColor="red"/>
		<paraStyle name="sum_float_end" fontName="Helvetica" alignment="right" textColor="red"/>
		<blockTableStyle id="table">
			<blockValign value="TOP"/>
			<blockFont name="Helvetica" size="12" start="0,0" stop="-1,0"/>
			<blockBackground colorName="(0.8,0.8,0.8)" start="0,0" stop="-1,0"/>

			<lineStyle kind="GRID" colorName="lightgrey" thickness="0.3"/>

			<lineStyle kind="LINEBELOW" colorName="black" thickness="1.5" start="0,0" stop="-1,0"/>
			<lineStyle kind="LINEABOVE" colorName="black" thickness="1.5" start="0,0" stop="-1,0"/>
		</blockTableStyle>
	</stylesheet>
	<story>
		<blockTable style="table">
			<xsl:attribute name="colWidths">
				<xsl:value-of select="/report/config/tableSize"/>
			</xsl:attribute> 
			<xsl:apply-templates select="header"/>
			<xsl:apply-templates select="group"/>

			<xsl:if test="group//@sum">
				<tr>
					<xsl:for-each select="group[position()=1]/record[position()=1]/field">
						<xsl:choose>
							<xsl:when test="position()=1">
								<td><para style="sum_end">SUM</para></td>
							</xsl:when>
							<xsl:when test="@sum"> 
								<xsl:variable name="ici">
									<xsl:value-of select="@id"/>
								</xsl:variable> 
								<td><para style="sum_float_end"><xsl:value-of select="sum(../../../group/record/field[@id=$ici])"/></para></td>
							</xsl:when>
							<xsl:otherwise>
								<td/>
							</xsl:otherwise>
						</xsl:choose>
					</xsl:for-each>
				</tr>
			</xsl:if>
			<xsl:if test="group//@count">
				<tr>
					<xsl:for-each select="group[position()=1]/record[position()=1]/field">
						<xsl:choose>
							<xsl:when test="position()=1">
								<td><para style="sum_end">#</para></td>
							</xsl:when>
							<xsl:when test="@count"> 
								<xsl:variable name="ici">
									<xsl:value-of select="@id"/>
								</xsl:variable> 
								<td><para style="sum_float_end"><xsl:value-of select="count(../../../group/record/field[@id=$ici])"/></para></td>
							</xsl:when>
							<xsl:otherwise>
								<td/>
							</xsl:otherwise>
						</xsl:choose>
					</xsl:for-each>
				</tr>
			</xsl:if>
			<xsl:if test="group//@avg">
				<tr>
					<xsl:for-each select="group[position()=1]/record[position()=1]/field">
						<xsl:choose>
							<xsl:when test="position()=1">
								<td><para style="sum_end">AVG</para></td>
							</xsl:when>
							<xsl:when test="@avg"> 
								<xsl:variable name="ici">
									<xsl:value-of select="@id"/>
								</xsl:variable> 
								<td><para style="sum_float_end"><xsl:value-of select="sum(../../../group/record/field[@id=$ici]) div count(../../../group/record/field[@id=$ici])"/></para></td>
							</xsl:when>
							<xsl:otherwise>
								<td/>
							</xsl:otherwise>
						</xsl:choose>
					</xsl:for-each>
				</tr>
			</xsl:if>
		</blockTable>
	</story>
	</document>
</xsl:template>

<xsl:template match="header">
	<tr>
		<xsl:apply-templates select="field"/>
	</tr>
</xsl:template>

<xsl:template match="group">
	<xsl:if test="not(/report/config/totalonly)">
		<xsl:apply-templates select="record"/>
	</xsl:if>
	<xsl:if test="/report/config/groupby">
		<!-- SUM -->
		<xsl:if test="//@sum">
			<tr>
				<xsl:for-each select="record[position()=1]/field">
					<xsl:choose>
						<xsl:when test="/report/config/groupby = @id">
							<td><para style="sum"><xsl:value-of select="."/> (SUM)</para></td>
						</xsl:when>
						<xsl:when test="@sum"> 
							<xsl:variable name="ici">
								<xsl:value-of select="@id"/>
							</xsl:variable> 
							<td><para style="sum_float"><xsl:value-of select="sum(../../record/field[@id=$ici])"/></para></td>
						</xsl:when>
						<xsl:otherwise>
							<td/>
						</xsl:otherwise>
					</xsl:choose>
				</xsl:for-each>
			</tr>
		</xsl:if>
		<!-- COUNT -->
		<xsl:if test="//@count">
			<tr>
				<xsl:for-each select="record[position()=1]/field">
					<xsl:choose>
						<xsl:when test="/report/config/groupby = @id">
							<td><para style="sum"><xsl:value-of select="."/> (#)</para></td>
						</xsl:when>
						<xsl:when test="@count"> 
							<xsl:variable name="ici">
								<xsl:value-of select="@id"/>
							</xsl:variable> 
							<td><para style="sum_float"><xsl:value-of select="count(../../record/field[@id=$ici])"/></para></td>
						</xsl:when>
						<xsl:otherwise>
							<td/>
						</xsl:otherwise>
					</xsl:choose>
				</xsl:for-each>
			</tr>
		</xsl:if>
		<!-- AVG -->
		<xsl:if test="//@avg">
			<tr>
				<xsl:for-each select="record[position()=1]/field">
					<xsl:choose>
						<xsl:when test="/report/config/groupby = @id">
							<td><para style="sum"><xsl:value-of select="."/> (AVG)</para></td>
						</xsl:when>
						<xsl:when test="@avg"> 
							<xsl:variable name="ici">
								<xsl:value-of select="@id"/>
							</xsl:variable> 
							<td><para style="sum_float"><xsl:value-of select="sum(../../record/field[@id=$ici]) div count(../../record/field[@id=$ici])"/></para></td>
						</xsl:when>
						<xsl:otherwise>
							<td/>
						</xsl:otherwise>
					</xsl:choose>
				</xsl:for-each>
			</tr>
		</xsl:if>
	</xsl:if>
</xsl:template>

<xsl:template match="record">
	<tr>
		<xsl:apply-templates select="field"/>
	</tr>
</xsl:template>

<xsl:template match="field">
	<xsl:choose>
		<xsl:when test="@level">
			<td><pre><xsl:value-of select="@level"/><xsl:value-of select="."/></pre></td>
		</xsl:when>
		<xsl:otherwise>
			<td><para><xsl:value-of select="."/></para></td>
		</xsl:otherwise>
	</xsl:choose>
</xsl:template>

</xsl:stylesheet>
